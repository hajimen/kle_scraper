(function(){
    const NOP = 'nop';
    const REG_ROTATE = /rotate\((.*)deg\)/;


    window.retrieveTransforms = function() {
        let transforms = [];
        const kls = document.querySelectorAll(".keylabels");
        kls.forEach((kl, idx) => {
            const parent = kl.parentNode;
            let tr = NOP;
            if (parent.style.transform) {
                tr = parent.style.transform + '\n' + parent.style.transformOrigin;
            }
            if (! transforms.includes(tr)) {
                transforms.push(tr);
            }
        });
        return transforms;
    };

    window.retrieveRects = function(tr) {
        const b = document.querySelector("#screen_rotate");
        if (tr == NOP) {
            b.removeAttribute('style');
        } else {
            const trs = tr.split('\n');

            const deg_str = REG_ROTATE.exec(trs[0])[1];
            let rev_deg_str = '';
            if (deg_str.startsWith('-')) {
                rev_deg_str = deg_str.substring(1)
            } else {
                rev_deg_str = '-' + deg_str;
            }
            b.style.transform = 'rotate(' + rev_deg_str + 'deg)';
            b.style.transformOrigin = trs[1];
        }

        const kls = document.querySelectorAll(".keylabels");
        let rects = [];
        kls.forEach((kl, idx) => {
            const parent = kl.parentNode;
            let ctr = NOP;
            if (parent.style.transform) {
                ctr = parent.style.transform + '\n' + parent.style.transformOrigin;
            }
            if (ctr == tr) {
                const br = kl.getBoundingClientRect();
                if (br["top"] == 0 && br["bottom"] == 0 && br["left"] == 0 && br["right"] == 0) {
                } else {
                    rects.push([idx, br])
                }
            }
        });
        return rects;
    };
})();
