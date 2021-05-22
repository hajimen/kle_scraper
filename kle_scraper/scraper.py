import os
import typing as ty
import tempfile
import atexit
from PIL import Image
from cefpython3 import cefpython as cef
import pykle_serial as kle_serial

# web
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer
import threading


# Constant
NOP = 'nop'  # no operation

# Config
VIEWPORT_SIZE = (16000, 8000)  # enough large area to accommodate most designs.


def exit_scraping(browser):
    # Important note:
    #   Do not close browser nor exit app from OnLoadingStateChange
    #   OnLoadError or OnPaint events. Closing browser during these
    #   events may result in unexpected behavior. Use cef.PostTask
    #   function to call exit_scraping from these events.
    browser.CloseBrowser()
    cef.QuitMessageLoop()


class BrowserContext:
    def __init__(self, kle_json_filename: str, image_output_dir: str):
        self.kle_keyboard: kle_serial.Keyboard = None
        self.kle_json_filename = kle_json_filename
        self.image_output_dir = image_output_dir
        self.rects: ty.Any = None
        self.transforms: ty.Set[str] = set()
        self.capturing_screenshot = False
        self.current_transform: str = ''
        self.shot_transforms: ty.Set[str] = set()


def handle_exception(func):
    def wrapped(bc: BrowserContext, browser):
        try:
            return func(bc, browser)
        except:
            import traceback
            print("[kle_scraper] Uncaught exception raised.")
            traceback.print_exc()
            cef.PostTask(cef.TID_UI, exit_scraping, browser)
    return wrapped


@handle_exception
def exec_retrieve_rects(bc: BrowserContext, browser):
    bc.rects = None
    tr = bc.current_transform.replace('\n', r'\n')
    browser.ExecuteJavascript(r'''(function(){
        document.querySelectorAll(".keycap > div").forEach(e => {
            e.style.backgroundColor = "#ffffff";
        });
        document.querySelectorAll(".keytop").forEach(e => {
            e.style.borderColor = "#ffffff";
        });''' +
        f"yieldRects(window.retrieveRects('{tr}'));" +
    '''})();
    ''')
    cef.PostDelayedTask(cef.TID_UI, 100, wait_retrieve_rects, bc, browser)


@handle_exception
def wait_retrieve_transforms(bc: BrowserContext, browser):
    if bc.transforms is None:
        cef.PostDelayedTask(cef.TID_UI, 100, wait_retrieve_transforms, bc, browser)
    else:
        bc.current_transform = NOP
        exec_retrieve_rects(bc, browser)
        return


@handle_exception
def wait_retrieve_rects(bc: BrowserContext, browser):
    if bc.rects is None:
        cef.PostDelayedTask(cef.TID_UI, 100, wait_retrieve_rects, bc, browser)
        return

    cef.PostDelayedTask(cef.TID_UI, 500, delay_screenshot, bc, browser)


@handle_exception
def delay_screenshot(bc: BrowserContext, browser):
    bc.capturing_screenshot = True
    browser.Invalidate(cef.PET_VIEW)
    cef.PostDelayedTask(cef.TID_UI, 100, wait_screenshot, bc, browser)


@handle_exception
def wait_screenshot(bc: BrowserContext, browser):
    if bc.capturing_screenshot:
        cef.PostDelayedTask(cef.TID_UI, 100, wait_screenshot, bc, browser)
        return

    buffer_string = browser.GetUserData("OnPaint.buffer_string")
    if not buffer_string:
        raise Exception("buffer_string is empty, OnPaint never called?")

    image = Image.frombytes("RGBA", VIEWPORT_SIZE, buffer_string, "raw", "RGBA", 0, 1)

    # check bottom right pixel of rendered image
    _, _, _, rb_pixel_a = image.getpixel((VIEWPORT_SIZE[0] - 18, VIEWPORT_SIZE[1] - 18))
    if rb_pixel_a == 0:
        # Rendering is not completed. Capture again.
        bc.capturing_screenshot = True
        browser.Invalidate(cef.PET_VIEW)
        cef.PostDelayedTask(cef.TID_UI, 100, wait_screenshot, bc, browser)
        return

    # tr = bc.current_transform.replace('\n', '_')
    # image.save(os.path.join(bc.image_output_dir, f"full-{tr}.png"))
    for i, (idx, br) in enumerate(bc.rects):
        p = os.path.join(bc.image_output_dir, f"{str(idx)}.png")
        keylabel_image = image.crop([br['left'], br['top'], br['right'], br['bottom'], ])
        keylabel_image.save(p)
    bc.shot_transforms.add(bc.current_transform)
    rest_trs = bc.transforms - bc.shot_transforms
    if len(rest_trs) > 0:
        bc.current_transform = next(iter(rest_trs))
        exec_retrieve_rects(bc, browser)
        return

    with open(bc.kle_json_filename, 'r', encoding='utf-8') as f:
        json = f.read()
    bc.kle_keyboard = kle_serial.parse(json)

    cef.PostTask(cef.TID_UI, exit_scraping, browser)


class LoadHandler(object):
    def __init__(self, browser_context: BrowserContext):
        self.browser_context = browser_context

    def OnLoadingStateChange(self, browser, is_loading, **_):
        """Called when the loading state has changed."""
        try:
            if not is_loading:
                # Loading is complete
                def yield_transforms(transforms):
                    self.browser_context.transforms = set(transforms)

                def yield_rects(rects):
                    self.browser_context.rects = rects

                bindings = cef.JavascriptBindings(bindToFrames=False, bindToPopups=False)
                bindings.SetFunction("yieldTransforms", yield_transforms)
                bindings.SetFunction("yieldRects", yield_rects)
                browser.SetJavascriptBindings(bindings)
                with open(self.browser_context.kle_json_filename, 'r', encoding='utf-8') as f:
                    json = f.read()
                browser.ExecuteJavascript(r'''(function(){
                    window.deserializeAndRenderAndApply(''' + json + r''');
                    yieldTransforms(window.retrieveTransforms());
                })();
                ''')

                cef.PostDelayedTask(cef.TID_UI, 2000, wait_retrieve_transforms, self.browser_context, browser)
        except:
            import traceback
            print("[kle_scraper] ERROR: Failed in OnLoadingStateChange()")
            traceback.print_exc()
            cef.PostTask(cef.TID_UI, exit_scraping, browser)

    def OnLoadError(self, browser, frame, error_code, failed_url, **_):
        """Called when the resource load for a navigation fails or is canceled."""
        if not frame.IsMain():
            # We are interested only in loading main url.
            # Ignore any errors during loading of other frames.
            return
        print("[kle_scraper] ERROR: Failed to load url: {url}".format(url=failed_url))
        print("[kle_scraper] Error code: {code}".format(code=error_code))
        # See comments in exit_scraping() why PostTask must be used
        cef.PostTask(cef.TID_UI, exit_scraping, browser)


class RenderHandler(object):
    def __init__(self, browser_context: BrowserContext):
        self.browser_context = browser_context

    def GetViewRect(self, rect_out, **_):
        """Called to retrieve the view rectangle which is relative
        to screen coordinates. Return True if the rectangle was
        provided."""
        # rect_out --> [x, y, width, height]
        rect_out.extend([0, 0, VIEWPORT_SIZE[0], VIEWPORT_SIZE[1]])
        return True

    def OnPaint(self, browser, element_type, dirty_rects, paint_buffer, **_):
        """Called when an element should be painted."""
        try:
            if self.browser_context.capturing_screenshot and element_type == cef.PET_VIEW:
                if len(dirty_rects) == 0:
                    return
                dr = dirty_rects[0]
                if dr[0] != 0 or dr[1] != 0 or dr[2] != VIEWPORT_SIZE[0] or dr[3] != VIEWPORT_SIZE[1]:
                    # partial paint
                    return
                # Buffer string is a huge string, so for performance
                # reasons it would be better not to copy this string.
                # I think that Python makes a copy of that string when
                # passing it to SetUserData.
                buffer_string = paint_buffer.GetBytes(mode="rgba",
                                                      origin="top-left")
                # Browser object provides GetUserData/SetUserData methods
                # for storing custom data associated with browser.
                browser.SetUserData("OnPaint.buffer_string", buffer_string)
                self.browser_context.capturing_screenshot = False
        except:
            import traceback
            print("[kle_scraper] ERROR: Failed in OnPaint()")
            traceback.print_exc()
            cef.PostTask(cef.TID_UI, exit_scraping, browser)


def scrape(kle_json_filename: str, image_output_dir: str) -> kle_serial.Keyboard:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=os.path.join(os.path.abspath(os.path.dirname(__file__)), 'web'), **kwargs)

        def log_message(self, format, *args):
            pass

    try:
        tcp_server = TCPServer(('127.0.0.1', 0), Handler)
        tcp_server_thread = threading.Thread(target=tcp_server.serve_forever, daemon=True)
        tcp_server_thread.start()
        url = f"http://localhost:{str(tcp_server.server_address[1])}/index.html"

        browser_settings = {
            # Tweaking OSR performance (Issue #240)
            "windowless_frame_rate": 30,  # Default frame rate in CEF is 30
        }
        # Create browser in off-screen-rendering mode (windowless mode)
        # by calling SetAsOffscreen method. In such mode parent window
        # handle can be NULL (0).
        parent_window_handle = 0
        window_info = cef.WindowInfo()
        window_info.SetAsOffscreen(parent_window_handle)
        browser = cef.CreateBrowserSync(window_info=window_info,
                                        settings=browser_settings,
                                        url=url)
        bc = BrowserContext(kle_json_filename, image_output_dir)
        browser.SetClientHandler(LoadHandler(bc))
        browser.SetClientHandler(RenderHandler(bc))
        browser.SendFocusEvent(True)
        # You must call WasResized at least once to let know CEF that
        # viewport size is available and that OnPaint may be called.
        browser.WasResized()
        cef.MessageLoop()  # this call blocks thread.

        return bc.kle_keyboard
    finally:
        tcp_server.shutdown()


def init():
    # Off-screen-rendering requires setting "windowless_rendering_enabled"
    # option.
    settings = {
        "windowless_rendering_enabled": True,
        'cache_path': tempfile.gettempdir(),  # https://github.com/cztomczak/cefpython/issues/432
        # "debug": True,
        # "log_severity": cef.LOGSEVERITY_INFO,
    }
    switches = {
        # GPU acceleration is not supported in OSR mode, so must disable
        # it using these Chromium switches (Issue #240 and #463)
        "disable-gpu": "",
        "disable-gpu-compositing": "",
        # Tweaking OSR performance by setting the same Chromium flags
        # as in upstream cefclient (Issue #240).
        "enable-begin-frame-scheduling": "",
        "disable-surfaces": "",  # This is required for PDF ext to work
    }
    cef.Initialize(settings=settings, switches=switches)


@atexit.register
def exit():
    cef.Shutdown()


init()
