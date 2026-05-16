(function() {
    function D(h, z, j) {
        function F(Z, A) {
            if (!z[Z]) {
                if (!h[Z]) {
                    var q = "function" == typeof require && require;
                    if (!A && q) return q(Z, !0);
                    if (l) return l(Z, !0);
                    var Q = new Error("Cannot find module '" + Z + "'");
                    throw Q.code = "MODULE_NOT_FOUND", Q;
                }
                var I = z[Z] = {
                    exports: {}
                };
                h[Z][0].call(I.exports, (function(D) {
                    var z = h[Z][1][D];
                    return F(z || D);
                }), I, I.exports, D, h, z, j);
            }
            return z[Z].exports;
        }
        for (var l = "function" == typeof require && require, Z = 0; Z < j.length; Z++) F(j[Z]);
        return F;
    }
    return D;
})()({
    1: [ function(D, h, z) {
        "use strict";
        var j = void 0 && (void 0).__importDefault || function(D) {
            return D && D.__esModule ? D : {
                default: D
            };
        };
        Object.defineProperty(z, "__esModule", {
            value: true
        });
        const F = j(D("1p"));
        let l = false;
        (async () => {
            const D = await chrome.storage.local.get([ "global", "domains" ]), {host: h} = window.location;
            if (D.global && D.domains.includes(h)) (0, F.default)(), l = true;
            chrome.storage.onChanged.addListener((async D => {
                if ("domains" in D) if (D.domains.newValue.includes(h)) if (!l) (0, F.default)(),
                l = true;
            }));
        })();
    }, {
        "1p": 2
    } ],
    2: [ function(D, h, z) {
        "use strict";
        function j() {
            const D = document.createElement("style"), {head: h} = document;
            function z() {
                document.oncontextmenu = null, document.onselectstart = null, document.ondragstart = null,
                document.onmousedown = null, document.body.oncontextmenu = null, document.body.onselectstart = null,
                document.body.ondragstart = null, document.body.onmousedown = null, document.body.oncut = null,
                document.body.oncopy = null, document.body.onpaste = null, [].forEach.call([ "copy", "cut", "paste", "select", "selectstart" ], (D => {
                    document.addEventListener(D, (D => {
                        D.stopPropagation();
                    }), true);
                })), [].forEach.call([ "contextmenu", "copy", "cut", "paste", "mouseup", "mousedown", "keyup", "keydown", "drag", "dragstart", "select", "selectstart" ], (D => {
                    document.addEventListener(D, (D => {
                        D.stopPropagation();
                    }), true);
                })), h.appendChild(D);
            }
            function j() {
                this.events = [ "DOMAttrModified", "DOMNodeInserted", "DOMNodeRemoved", "DOMCharacterDataModified", "DOMSubtreeModified" ],
                this.bind();
            }
            function F(D) {
                this.event = D, this.contextmenuEvent = this.createEvent(this.event.type);
            }
            D.innerText = `* {\n      -webkit-user-select: text !important;\n      -moz-user-select: text !important;\n      -ms-user-select: text !important;\n       user-select: text !important;\n  }`,
            (async () => {
                while (!document.body) await new Promise((D => setTimeout(D, 100)));
                z();
            })(), j.prototype.bind = function D() {
                this.events.forEach((D => {
                    document.addEventListener(D, this, true);
                }));
            }, j.prototype.handleEvent = function D() {
                this.isCalled = true;
            }, j.prototype.unbind = function D() {
                this.events.forEach((() => {}));
            }, F.prototype.createEvent = function D(h) {
                const {target: z} = this.event, j = z.ownerDocument.createEvent("MouseEvents");
                return j.initMouseEvent(h, this.event.bubbles, this.event.cancelable, z.ownerDocument.defaultView, this.event.detail, this.event.screenX, this.event.screenY, this.event.clientX, this.event.clientY, this.event.ctrlKey, this.event.altKey, this.event.shiftKey, this.event.metaKey, this.event.button, this.event.relatedTarget),
                j;
            }, F.prototype.fire = function D() {
                const {target: h} = this.event;
                h.dispatchEvent(this.contextmenuEvent), this.isCanceled = this.contextmenuEvent.defaultPrevented;
            }, window.addEventListener("contextmenu", (function D(h) {
                h.stopPropagation(), h.stopImmediatePropagation();
                const z = new F(h);
                window.removeEventListener(h.type, D, true);
                const j = new F((() => {}));
                if (z.fire(), window.addEventListener(h.type, D, true), z.isCanceled && j.isCalled) h.preventDefault();
            }), true);
        }
        Object.defineProperty(z, "__esModule", {
            value: true
        }), z.default = j;
    }, {} ]
}, {}, [ 1 ]);