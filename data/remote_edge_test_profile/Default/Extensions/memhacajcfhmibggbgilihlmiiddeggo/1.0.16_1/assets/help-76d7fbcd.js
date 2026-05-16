import "./modulepreload-polyfill-7faf532e.js";
import { d as defineComponent, r as ref, o as onMounted, a as openBlock, c as createElementBlock, b as createBaseVNode, u as unref, e as createTextVNode, t as toDisplayString, _ as _export_sfc, f as createApp } from "./_plugin-vue_export-helper-2f49cf34.js";
import { i as installer } from "./index-dd0066b9.js";
import { l as logoPath, b as brandPath, p as productName, k as key } from "./config-b5aec82c.js";
import { a as getAltKeyText } from "./common-54d607d2.js";
import { b as browserPolyfillExports } from "./browser-polyfill-1bf53692.js";
import "./shim-5b326084.js";
import "./_commonjsHelpers-7a77ea84.js";
const _hoisted_1 = { class: "container" };
const _hoisted_2 = { class: "header" };
const _hoisted_3 = { class: "brand" };
const _hoisted_4 = { class: "icon" };
const _hoisted_5 = ["src"];
const _hoisted_6 = { class: "text" };
const _hoisted_7 = ["src"];
const _hoisted_8 = { class: "main" };
const _hoisted_9 = { class: "headline" };
const _hoisted_10 = { class: "item" };
const _hoisted_11 = { class: "helps" };
const _hoisted_12 = { class: "step" };
const _hoisted_13 = { class: "tips" };
const _hoisted_14 = { class: "image" };
const _hoisted_15 = ["src"];
const _hoisted_16 = { class: "step" };
const _hoisted_17 = { class: "tips" };
const _hoisted_18 = { class: "image" };
const _hoisted_19 = ["src"];
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "App",
  setup(__props) {
    const currentText = ref("文章");
    const items = ["文章", "对话框", "推文"];
    let index = 0;
    onMounted(() => {
      setInterval(() => {
        currentText.value = items[index];
        index = (index + 1) % items.length;
      }, 1500);
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          createBaseVNode("div", _hoisted_3, [
            createBaseVNode("div", _hoisted_4, [
              createBaseVNode("img", {
                src: unref(browserPolyfillExports).runtime.getURL(unref(logoPath))
              }, null, 8, _hoisted_5)
            ]),
            createBaseVNode("div", _hoisted_6, [
              createBaseVNode("img", {
                src: unref(browserPolyfillExports).runtime.getURL(unref(brandPath))
              }, null, 8, _hoisted_7)
            ])
          ])
        ]),
        createBaseVNode("div", _hoisted_8, [
          createBaseVNode("div", _hoisted_9, [
            createTextVNode("一键翻译网页中的"),
            createBaseVNode("span", _hoisted_10, toDisplayString(currentText.value), 1)
          ]),
          createBaseVNode("div", _hoisted_11, [
            createBaseVNode("div", _hoisted_12, [
              createBaseVNode("div", _hoisted_13, toDisplayString(`Step 1: 将${unref(productName)}添加到收藏以便随时访问`), 1),
              createBaseVNode("div", _hoisted_14, [
                createBaseVNode("img", {
                  img: "",
                  src: unref(browserPolyfillExports).runtime.getURL("s1.png")
                }, null, 8, _hoisted_15)
              ])
            ]),
            createBaseVNode("div", _hoisted_16, [
              createBaseVNode("div", _hoisted_17, toDisplayString(`Step 2: 选择合适的翻译服务，按下按钮或者使用快捷键：${unref(getAltKeyText)()} + ${unref(key).toUpperCase()}`), 1),
              createBaseVNode("div", _hoisted_18, [
                createBaseVNode("img", {
                  img: "",
                  src: unref(browserPolyfillExports).runtime.getURL("s2.png")
                }, null, 8, _hoisted_19)
              ])
            ])
          ])
        ])
      ]);
    };
  }
});
const App_vue_vue_type_style_index_0_scoped_066e63a5_lang = "";
const App = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-066e63a5"]]);
const style = "";
const app = createApp(App);
app.use(installer);
app.mount("#app");
