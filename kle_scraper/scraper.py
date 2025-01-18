import os
from pathlib import Path
import typing as ty
import sys
import atexit
import time
import ctypes
from PIL import Image as PilImageModule, ImageChops
from PIL.Image import Image
from cef_capi import header, struct, task_factory, handler, cef_pointer_to_struct, cef_string_ctor, base_ctor, cef_string_t, decode_cef_string, size_ctor
from cef_capi.app_client import client_ctor, settings_main_args_ctor
import pykle_serial as kle_serial

# Web
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import threading
from dataclasses import dataclass, field


# Constant
NOP = 'nop'  # no operation. See p2ppcb.js.

# Config
VIEWPORT_SIZE = (16000, 8000)  # enough large area to accommodate most designs.
TIMEOUT_SEC = 5.  # Infinite loop detection threshold

# To pass from render thread to browser threads.
BC_DEPOT: dict[int, 'BrowserContext'] = {}


@dataclass
class BrowserContext:
    rects: list[tuple[int, dict[str, float]]] | None = None
    transforms: set[str] = field(default_factory=set)
    capturing_screenshot = False
    current_transform: str = ''
    shot_transforms: set[str] = field(default_factory=set)
    last_image: Image | None = None


def browse(kle_json_file: Path, image_output_dir: Path, url: str, bc: BrowserContext) -> kle_serial.Keyboard:
    '''
    Creates browser, scrapes the image, and close the browser.
    '''
    # Timeout
    last_task_name = ''
    last_task_first_called_at = -1.

    # Given cef_browser_t instance of on_loading_state_change() / on_load_error().
    _saved_browser: struct.cef_browser_t | None = None

    def get_saved_browser() -> struct.cef_browser_t:
        if _saved_browser is None:
            # Never occurs
            raise Exception('_saved_browser is None.')
        return _saved_browser

    def get_browser_host():
        browser = get_saved_browser()
        browser_host_p = ctypes.cast(
            browser.get_host(browser),
            ctypes.POINTER(struct.cef_browser_host_t))
        return browser_host_p.contents

    @task_factory
    def exit_scraping():
        bh = get_browser_host()
        bh.close_browser(bh, 0)

    _saved_exception: Exception | None = None

    def handle_exception(func: ty.Callable):
        def wrapped(*args, **kwargs):
            nonlocal _saved_exception, last_task_name, last_task_first_called_at
            try:
                fn = func.__name__
                if fn.startswith('wait_'):
                    if fn != last_task_name:
                        last_task_name = func.__name__
                        last_task_first_called_at = time.perf_counter()
                    elif time.perf_counter() - last_task_first_called_at > TIMEOUT_SEC:
                        raise Exception('Timeout by infinite loop.')
                elif fn.startswith('exec_'):
                    last_task_name = ''
                return func(*args, **kwargs)
            except Exception as e:
                _saved_exception = e
                header.cef_post_task(header.TID_UI, exit_scraping())
        wrapped.__name__ = func.__name__
        return wrapped

    def execute_java_script(script: str):
        browser = get_saved_browser()

        frame = cef_pointer_to_struct(
            browser.get_main_frame(browser),
            struct.cef_frame_t)

        frame.execute_java_script(
            frame,
            cef_string_ctor(script),
            None,
            0
        )

    @task_factory
    @handle_exception
    def exec_retrieve_transform():
        with open(kle_json_file, 'r', encoding='utf-8') as f:
            json = f.read()

        execute_java_script(r'''
            (function(){
                window.deserializeAndRenderAndApply(''' + json + r''');
                kle_extension_obj.yieldTransforms("''' + str(id(bc)) + '''", window.retrieveTransforms());
            })();
        ''')
        header.cef_post_delayed_task(header.TID_UI, wait_retrieve_transforms(), 200)

    def retrieve_rects():
        bc.rects = None
        tr = bc.current_transform.replace('\n', r'\n')
        execute_java_script(r'''
            (function(){
                document.querySelectorAll(".keycap > div").forEach(e => {
                    e.style.backgroundColor = "#ffffff";
                });
                document.querySelectorAll(".keytop").forEach(e => {
                    e.style.borderColor = "#ffffff";
                });
                kle_extension_obj.yieldRects("''' + str(id(bc)) + '''", window.retrieveRects("''' + tr + '''"));
            })();
        ''')
        # Why 500 ms? `e.style.borderColor` requires long time to be rendered.
        header.cef_post_delayed_task(header.TID_UI, wait_retrieve_rects(), 500)

    @task_factory
    @handle_exception
    def wait_retrieve_transforms():
        if bc.transforms is None:
            header.cef_post_delayed_task(header.TID_UI, wait_retrieve_transforms(), 100)
        else:
            bc.current_transform = NOP
            retrieve_rects()

    def invalidate():
        bc.capturing_screenshot = True
        bh = get_browser_host()
        bh.invalidate(bh, header.PET_VIEW)
        header.cef_post_delayed_task(header.TID_UI, wait_screenshot(), 100)

    @task_factory
    @handle_exception
    def wait_retrieve_rects():
        if bc.rects is None:
            header.cef_post_delayed_task(header.TID_UI, wait_retrieve_rects(), 100)
            return

        invalidate()

    # Given bitmap of on_paint() handler.
    saved_buffer: ctypes.c_void_p | None = None

    @task_factory
    @handle_exception
    def wait_screenshot():
        if bc.capturing_screenshot:
            header.cef_post_delayed_task(header.TID_UI, wait_screenshot(), 100)
            return

        if saved_buffer is None:
            raise Exception("on_paint never called?")

        bstr = ctypes.string_at(saved_buffer, VIEWPORT_SIZE[0] * VIEWPORT_SIZE[1] * 4)
        pil_image = PilImageModule.frombytes('RGBA', (VIEWPORT_SIZE[0], VIEWPORT_SIZE[1]), bstr, 'raw', 'BGRA')

        # check bottom right pixel of rendered image
        _, _, _, rb_pixel_a = pil_image.getpixel((VIEWPORT_SIZE[0] - 18, VIEWPORT_SIZE[1] - 18))
        if rb_pixel_a == 0:
            # Rendering is not completed. Capture again.
            invalidate()
            return

        pil_image = pil_image.convert('RGB')

        if bc.last_image is not None and not ImageChops.difference(pil_image, bc.last_image).getbbox():
            # should be different from last image
            invalidate()
            return

        # tr = bc.current_transform.replace('\n', '_')
        # image.save(os.path.join(image_output_dir, f"full-{tr}.png"))
        if bc.rects is None:
            raise Exception('never')
        for i, (idx, br) in enumerate(bc.rects):
            p = os.path.join(image_output_dir, f"{str(idx)}.png")
            keylabel_image = pil_image.crop([br['left'], br['top'], br['right'], br['bottom'], ])
            keylabel_image.save(p)
        bc.shot_transforms.add(bc.current_transform)
        rest_trs = bc.transforms - bc.shot_transforms
        if len(rest_trs) > 0:
            bc.current_transform = next(iter(rest_trs))
            bc.last_image = pil_image
            retrieve_rects()
            return

        header.cef_post_task(header.TID_UI, exit_scraping())

    client = client_ctor()

    @handler(client)
    def get_load_handler(*_):
        load_handler = base_ctor(struct.cef_load_handler_t)

        @handler(load_handler)
        def on_loading_state_change(
                browser: struct.cef_browser_t,
                is_loading: int,
                can_go_back: int,
                can_go_forward: int):

            if is_loading:
                return
            nonlocal _saved_browser
            _saved_browser = browser
            header.cef_post_delayed_task(header.TID_UI, exec_retrieve_transform(), 200)

        @handler(load_handler)
        def on_load_error(
                browser: struct.cef_browser_t,
                frame: struct.cef_frame_t,
                error_code: int,
                error_text: cef_string_t,
                failed_url: cef_string_t):

            if not frame.is_main(frame):
                # We are interested only in loading main url.
                # Ignore any errors during loading of other frames.
                return
            nonlocal _saved_exception
            failed_url_py = decode_cef_string(failed_url)
            error_text_py = decode_cef_string(error_text)
            _saved_exception = Exception(
                f'Failed to load.\nURL: {failed_url_py}\nError code: {error_code}\nError text: {error_text_py}')
            header.cef_post_task(header.TID_UI, exit_scraping())
        
        return load_handler

    @handler(client)
    def get_render_handler(*_):
        render_handler = base_ctor(struct.cef_render_handler_t)

        @handler(render_handler, raw_arg_indices={4})
        def on_paint(
                browser: struct.cef_browser_t,
                element_type: int,
                dirty_rects_count: int,
                dirty_rects: ctypes._Pointer,  # ctypes.POINTER(struct.cef_rect_t)
                buffer: ctypes.c_void_p,
                width: int,
                height: int):

            nonlocal saved_buffer

            if not bc.capturing_screenshot or element_type != header.PET_VIEW:
                return
            if dirty_rects_count == 0:
                return

            dr: struct.cef_rect_t = dirty_rects[0]
            if dr.x != 0 or dr.y != 0 or dr.width != VIEWPORT_SIZE[0] or dr.height != VIEWPORT_SIZE[1]:
                # partial paint
                return
            saved_buffer = buffer
            bc.capturing_screenshot = False

        @handler(render_handler)
        def get_view_rect(
                browser: struct.cef_browser_t,
                rect: struct.cef_rect_t):

            rect.x = 0
            rect.y = 0
            rect.width = VIEWPORT_SIZE[0]
            rect.height = VIEWPORT_SIZE[1]
            return 1

        return render_handler

    window_info = struct.cef_window_info_t()
    window_info.windowless_rendering_enabled = 1

    browser_settings = size_ctor(struct.cef_browser_settings_t)

    br: struct.cef_browser_t = header.cef_browser_host_create_browser_sync(
        window_info,
        client,
        cef_string_ctor(url),
        browser_settings,
        None,
        None
    ).contents

    # `header.cef_run_message_loop()` crashes in second run. I don't know why.
    while br.is_valid(br) and _saved_exception is None:
        header.cef_do_message_loop_work()

    if _saved_exception is not None:
        raise _saved_exception

    with open(kle_json_file, 'r', encoding='utf-8') as f:
        json = f.read()
    return kle_serial.parse(json)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=os.path.join(os.path.abspath(os.path.dirname(__file__)), 'web'), **kwargs)

    def log_message(self, format, *args):
        pass


def scrape(
        kle_json_file: ty.Union[os.PathLike, str],
        image_output_dir: ty.Union[os.PathLike, str]) -> kle_serial.Keyboard:

    bc = BrowserContext()
    BC_DEPOT[id(bc)] = bc

    try:
        tcp_server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        tcp_server_thread = threading.Thread(target=tcp_server.serve_forever, daemon=True)
        tcp_server_thread.start()
        url = f"http://localhost:{str(tcp_server.server_address[1])}/index.html"

        return browse(
            Path(kle_json_file),
            Path(image_output_dir),
            url,
            bc
        )
    finally:
        tcp_server.shutdown()
        del BC_DEPOT[id(bc)]


def init():
    app = base_ctor(struct.cef_app_t)

    @handler(app)
    def on_before_command_line_processing(
            process_type: cef_string_t,
            command_line: struct.cef_command_line_t):

        command_line.append_switch(command_line, cef_string_ctor('single-process'))

        # https://stackoverflow.com/questions/79094715/disable-hardware-influence-on-playwright-tests-using-chromium-driver
        command_line.append_switch(command_line, cef_string_ctor('disable-lcd-text'))

        command_line.append_switch(command_line, cef_string_ctor('disable-gpu'))
        command_line.append_switch(command_line, cef_string_ctor('disable-gpu-compositing'))
        command_line.append_switch(command_line, cef_string_ctor('in-process-gpu'))
        if sys.platform == 'darwin':
            # Disable the toolchain prompt on macOS.
            command_line.append_switch(command_line, cef_string_ctor('use-mock-keychain'))

    settings, main_args = settings_main_args_ctor()
    settings.log_severity = struct.LOGSEVERITY_DISABLE
    settings.no_sandbox = 1
    settings.windowless_rendering_enabled = 1

    v8handler = base_ctor(struct.cef_v8handler_t)

    @handler(v8handler, raw_arg_indices={4, 5})
    def execute(
            name: cef_string_t,
            object: struct.cef_v8value_t,
            arguments_count: int,
            arguments: ctypes._Pointer,  # ctypes.POINTER(ctypes.POINTER(struct.cef_v8value_t))
            retval: ctypes._Pointer,  # ctypes.POINTER(ctypes.POINTER(struct.cef_v8value_t))
            exception: cef_string_t):
        '''
        CAUTION: Python debugger cannot make a breakpoint in this handler.
        '''
        if arguments_count != 2:
            raise Exception('never')

        a: struct.cef_v8value_t = arguments[0].contents
        if not a.is_string(a):
            raise Exception('arg 0 should be string')
        # get_string_value() returns userfree instance pointer.
        id_bc = int(decode_cef_string(a.get_string_value(a), free_after_decode=True))
        if id_bc not in BC_DEPOT:
            raise Exception('unknown id of BC_DEPOT')
        bc = BC_DEPOT[id_bc]

        a = arguments[1].contents
        if not a.is_array(a):
            raise Exception('arg 1 should be array')

        match decode_cef_string(name):
            case 'yieldTransforms':
                transforms: set[str] = set()
                for ptr in [a.get_value_byindex(a, i) for i in range(a.get_array_length(a))]:
                    tr: struct.cef_v8value_t = cef_pointer_to_struct(ptr, struct.cef_v8value_t)
                    if not tr.is_string(tr):
                        raise Exception('tr should be string')
                    transforms.add(decode_cef_string(tr.get_string_value(tr), free_after_decode=True))
                bc.transforms = transforms
            case 'yieldRects':
                rects: list[tuple[int, dict[str, float]]] = []
                for pr in [a.get_value_byindex(a, i) for i in range(a.get_array_length(a))]:
                    r: struct.cef_v8value_t = cef_pointer_to_struct(pr, struct.cef_v8value_t)
                    if not r.is_array(r) or r.get_array_length(r) != 2:
                        raise Exception('r should be array size==2')

                    idx = cef_pointer_to_struct(r.get_value_byindex(r, 0), struct.cef_v8value_t)
                    if not idx.is_int(idx):
                        raise Exception('idx should be int')
                    idx_py: int = idx.get_int_value(idx)

                    br = cef_pointer_to_struct(r.get_value_byindex(r, 1), struct.cef_v8value_t)
                    if not br.is_object(br):
                        raise Exception('br should be object')
                    br_py: dict[str, float] = {}
                    for k in ['left', 'right', 'top', 'bottom']:
                        lrtb = cef_pointer_to_struct(br.get_value_bykey(
                            br,
                            cef_string_ctor(k)
                        ), struct.cef_v8value_t)
                        if not lrtb.is_double(lrtb):
                            raise Exception('lrtb should be double')
                        br_py[k] = float(lrtb.get_double_value(lrtb))

                    rects.append((idx_py, br_py))
                bc.rects = rects
            case _:
                # Never occurs
                raise Exception('Unknown function called.')
        return 1

    @handler(app)
    def get_render_process_handler():
        render_process_handler = base_ctor(struct.cef_render_process_handler_t)

        @handler(render_process_handler)
        def on_web_kit_initialized(*_):
            header.cef_register_extension(
                cef_string_ctor('v8/kle_extension'),
                cef_string_ctor('''
                    var kle_extension_obj = {};
                    (function(){
                        kle_extension_obj.yieldTransforms = function(id_bc, x){
                            native function yieldTransforms(id_bc, x);
                            return yieldTransforms(id_bc, x);
                        };
                        kle_extension_obj.yieldRects = function(id_bc, x){
                            native function yieldRects(id_bc, x);
                            return yieldRects(id_bc, x);
                        };
                    })();
                '''), v8handler)
            return 0

        return render_process_handler

    header.cef_initialize(main_args, settings, app, None)


@atexit.register
def exit():
    header.cef_shutdown()


init()
