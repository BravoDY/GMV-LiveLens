import "./modulepreload-polyfill-7faf532e.js";
import "./str.ts-d3a40573.js";
import { _ as _export_sfc, a as openBlock, c as createElementBlock, b as createBaseVNode, F as Fragment, l as renderList, q as normalizeClass, t as toDisplayString, s as renderSlot, p as pushScopeId, n as popScopeId, d as defineComponent, r as ref, v as watchEffect, x as computed, o as onMounted, g as resolveComponent, u as unref, m as createVNode, w as withCtx, e as createTextVNode, f as createApp } from "./_plugin-vue_export-helper-2f49cf34.js";
import { E as ElMessage, i as installer } from "./index-dd0066b9.js";
import { b as browserPolyfillExports } from "./browser-polyfill-1bf53692.js";
import { g as getUserConfig, t as track, u as updateUserConfig } from "./common-54d607d2.js";
import { h as hightlightStyle, l as logoPath, b as brandPath } from "./config-b5aec82c.js";
import { S as StyleInjector } from "./styleInject-0584f937.js";
import { s as setOffscreen, a as shouldUpdate } from "./service-ba894d8a.js";
import "./_commonjsHelpers-7a77ea84.js";
import "./shim-5b326084.js";
const _sfc_main$1 = {
  name: "Tab",
  props: {
    defaultIndex: {
      type: Number,
      default: 0
    }
  },
  data() {
    return {
      activeIndex: this.defaultIndex,
      items: [
        {
          name: "setting",
          title: "基本设置"
        },
        {
          name: "help",
          title: "帮助说明"
        }
      ]
    };
  },
  provide() {
    return {
      registerTab: this.registerTab,
      activeIndex: this.activeIndex
    };
  },
  methods: {
    registerTab(item) {
      this.items.push(item);
    },
    async move(index) {
      if (index === 1) {
        const website = "https://magicfanyi.youdao.com/#/help";
        await browserPolyfillExports.runtime.sendMessage({ action: "openNewTab", url: website });
        return 0;
      }
      this.activeIndex = index;
    }
  }
};
const Tab_vue_vue_type_style_index_0_scoped_6161a2a4_lang = "";
const _withScopeId$1 = (n) => (pushScopeId("data-v-6161a2a4"), n = n(), popScopeId(), n);
const _hoisted_1$1 = { class: "tab" };
const _hoisted_2$1 = {
  class: "tab-header",
  id: "tab-header"
};
const _hoisted_3$1 = /* @__PURE__ */ _withScopeId$1(() => /* @__PURE__ */ createBaseVNode("div", { class: "headline" }, " 菜单 ", -1));
const _hoisted_4$1 = ["onClick"];
const _hoisted_5$1 = { class: "tab-content" };
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  var _a;
  return openBlock(), createElementBlock("div", _hoisted_1$1, [
    createBaseVNode("div", _hoisted_2$1, [
      _hoisted_3$1,
      (openBlock(true), createElementBlock(Fragment, null, renderList($data.items, (item, index) => {
        return openBlock(), createElementBlock("div", {
          key: index,
          class: normalizeClass({ "tab-header-item": true, "active": $data.activeIndex === index }),
          onClick: ($event) => $options.move(index)
        }, toDisplayString(item.title), 11, _hoisted_4$1);
      }), 128))
    ]),
    createBaseVNode("div", _hoisted_5$1, [
      renderSlot(_ctx.$slots, (_a = $data.items[$data.activeIndex]) == null ? void 0 : _a.name, {}, void 0, true)
    ])
  ]);
}
const Tab = /* @__PURE__ */ _export_sfc(_sfc_main$1, [["render", _sfc_render], ["__scopeId", "data-v-6161a2a4"]]);
const _withScopeId = (n) => (pushScopeId("data-v-aa470d26"), n = n(), popScopeId(), n);
const _hoisted_1 = { class: "container" };
const _hoisted_2 = { class: "header" };
const _hoisted_3 = { class: "brand" };
const _hoisted_4 = { class: "icon" };
const _hoisted_5 = ["src"];
const _hoisted_6 = { class: "text" };
const _hoisted_7 = ["src"];
const _hoisted_8 = { class: "main" };
const _hoisted_9 = { class: "translateStyle" };
const _hoisted_10 = { class: "configInfo" };
const _hoisted_11 = { class: "imgtrContainer" };
const _hoisted_12 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("div", { class: "explain" }, [
  /* @__PURE__ */ createBaseVNode("div", null, "功能说明:"),
  /* @__PURE__ */ createBaseVNode("p", { class: "line" }, "当图片翻译或者音频翻译导致问题时候使用本按钮关闭!!"),
  /* @__PURE__ */ createBaseVNode("p", { class: "line" }, "需要开启图片翻译, 直接对图片右键翻译即可开启!!"),
  /* @__PURE__ */ createBaseVNode("p", { class: "line" }, "需要开启音频翻译, 直接进入翻译界面即可!!")
], -1));
const _hoisted_13 = { class: "action" };
const _hoisted_14 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("ul", null, [
  /* @__PURE__ */ createBaseVNode("li", null, "X Spaces"),
  /* @__PURE__ */ createBaseVNode("li", null, "其他，敬请期待。。。")
], -1));
const _hoisted_15 = { class: "imgtrContainer" };
const _hoisted_16 = { class: "explain" };
const _hoisted_17 = { class: "line" };
const _hoisted_18 = { class: "action" };
const _hoisted_19 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("iframe", { src: "http://localhost:5173/#/help" }, null, -1));
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "App",
  setup(__props) {
    const updateInfoTime = ref(0);
    const styleInjector = new StyleInjector("", hightlightStyle);
    const tabPosition = ref("left");
    const highLightStyle = ref(0);
    const num = ref(1);
    const inlineTranslate = ref(true);
    const aiLabel = ref(true);
    const configLoading = ref(false);
    ref(false);
    const command = ref([]);
    function timestampToReadableDate(timestamp) {
      const date = new Date(timestamp);
      const options = {
        year: "numeric",
        month: "long",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      };
      return date.toLocaleString("zh-CN", options);
    }
    watchEffect(async () => {
      const commands = await browserPolyfillExports.commands.getAll();
      command.value = commands.slice(1);
    });
    const goSetting = async () => {
      try {
        await track(window, "goSetting", {});
      } catch (error) {
        console.error(error);
      }
      await browserPolyfillExports.runtime.sendMessage({ action: "openNewTab", url: `chrome://extensions/shortcuts` });
    };
    const closeImgTr = async () => {
      await setOffscreen(false);
    };
    const updateTimeString = computed(() => {
      return `最后更新时间；${timestampToReadableDate(updateInfoTime.value)}`;
    });
    const clear = async () => {
      await browserPolyfillExports.runtime.sendMessage({
        action: "clear"
      });
      ElMessage({
        message: "清理翻译缓存成功",
        type: "success"
      });
    };
    const changeHighLightStyle = async (value) => {
      console.log(value);
      try {
        await track(window, "changeHighLightStyle", {
          highLightStyle: value
        });
      } catch (error) {
        console.error(error);
      }
      highLightStyle.value = value;
      if (typeof styleInjector.hightlightStyle[value] === "string") {
        styleInjector.removeClass("yd-highlight");
        styleInjector.addClass("yd-highlight", styleInjector.hightlightStyle[value]);
      } else {
        styleInjector.removeClass("yd-highlight");
        styleInjector.addClass("yd-highlight", styleInjector.hightlightStyle[value].original);
        styleInjector.removeClass("yd-highlight:hover");
        styleInjector.addClass("yd-highlight:hover", styleInjector.hightlightStyle[value].hover);
      }
      const config = await getUserConfig();
      config.highLightStyle = value;
      await updateUserConfig(config);
      ElMessage({
        message: "设置翻译样式成功",
        type: "success"
      });
    };
    const changeRetries = async (value) => {
      num.value = value;
      try {
        await track(window, "changeRetries", {
          changeRetries: value
        });
      } catch (error) {
        console.error(error);
      }
      const config = await getUserConfig();
      config.retries = value;
      await updateUserConfig(config);
      ElMessage({
        message: "设置重试设置成功",
        type: "success"
      });
    };
    const updateRules = async () => {
      try {
        await track(window, "forceUpdateRules");
      } catch (error) {
        console.error(error);
      }
      configLoading.value = true;
      try {
        await shouldUpdate(0);
        const config = await getUserConfig();
        updateInfoTime.value = config.configUpdateTime;
      } catch (error) {
        console.error(error);
      } finally {
        configLoading.value = false;
      }
    };
    const changeInlineTranslate = async (value) => {
      inlineTranslate.value = value;
      try {
        await track(window, "inlineTranslate", {
          inlineTranslate: value
        });
      } catch (error) {
        console.error(error);
      }
      const config = await getUserConfig();
      config.inlineTranslate = value;
      await updateUserConfig(config);
      ElMessage({
        message: `${value ? "开启" : "关闭"}设置对话框翻译`,
        type: "success"
      });
    };
    const changeAiLabel = async (value) => {
      try {
        await track(window, "aiLabel", {
          aiLabel: value
        });
      } catch (error) {
        console.error(error);
      }
      aiLabel.value = value;
      const config = await getUserConfig();
      config.aiLabel = value;
      await updateUserConfig(config);
      ElMessage({
        message: `${value ? "开启" : "关闭"}追加AI大模型翻译`,
        type: "success"
      });
    };
    const updateConfig = async () => {
      const config = await getUserConfig();
      updateInfoTime.value = config.configUpdateTime;
      highLightStyle.value = config.highLightStyle;
      num.value = config.retries;
      inlineTranslate.value = config.inlineTranslate;
      aiLabel.value = config.aiLabel;
    };
    browserPolyfillExports.storage.local.onChanged.addListener((changes, areaName) => {
      updateConfig();
    });
    browserPolyfillExports.storage.sync.onChanged.addListener((changes, areaName) => {
      updateConfig();
    });
    onMounted(async () => {
      styleInjector.injectStyle(document.body);
      updateConfig();
      const screenWidth = window.visualViewport.width;
      if (screenWidth < 700) {
        tabPosition.value = "top";
      }
    });
    return (_ctx, _cache) => {
      const _component_el_option = resolveComponent("el-option");
      const _component_el_select = resolveComponent("el-select");
      const _component_el_form_item = resolveComponent("el-form-item");
      const _component_font = resolveComponent("font");
      const _component_el_input_number = resolveComponent("el-input-number");
      const _component_el_button = resolveComponent("el-button");
      const _component_el_switch = resolveComponent("el-switch");
      const _component_el_form = resolveComponent("el-form");
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
          createVNode(Tab, null, {
            setting: withCtx(() => [
              createVNode(_component_el_form, {
                "label-width": "120px",
                "label-position": "top",
                class: "custom-form"
              }, {
                default: withCtx(() => [
                  createVNode(_component_el_form_item, {
                    label: "翻译样式",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_select, {
                        placeholder: "样式",
                        modelValue: highLightStyle.value,
                        "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => highLightStyle.value = $event),
                        onChange: changeHighLightStyle
                      }, {
                        default: withCtx(() => [
                          createVNode(_component_el_option, {
                            label: "无",
                            value: 0
                          }),
                          createVNode(_component_el_option, {
                            label: "下划线",
                            value: 1
                          }),
                          createVNode(_component_el_option, {
                            label: "黄色高亮",
                            value: 2
                          }),
                          createVNode(_component_el_option, {
                            label: "模糊模式",
                            value: 3
                          })
                        ]),
                        _: 1
                      }, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createBaseVNode("div", _hoisted_9, [
                    createVNode(_component_font, { class: "yd-highlight" }, {
                      default: withCtx(() => [
                        createTextVNode(" 轻轻的我走了， 正如我轻轻的来； 我轻轻的招手， 作别西天的云彩。 那河畔的金柳， 是夕阳中的新娘； 波光里的艳影， 在我的心头荡漾。 ")
                      ]),
                      _: 1
                    })
                  ]),
                  createVNode(_component_el_form_item, {
                    label: "重试次数",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_input_number, {
                        modelValue: num.value,
                        "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => num.value = $event),
                        min: 0,
                        max: 3,
                        onChange: changeRetries
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "缓存",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_button, {
                        id: "clearCache",
                        type: "danger",
                        size: "small",
                        onClick: clear
                      }, {
                        default: withCtx(() => [
                          createTextVNode("清理翻译缓存")
                        ]),
                        _: 1
                      })
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "更新配置",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_button, {
                        id: "updateConfig",
                        onClick: updateRules,
                        loading: configLoading.value
                      }, {
                        default: withCtx(() => [
                          createTextVNode("立即更新")
                        ]),
                        _: 1
                      }, 8, ["loading"]),
                      createTextVNode(),
                      createBaseVNode("span", _hoisted_10, toDisplayString(updateTimeString.value), 1)
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "对话框翻译(需要刷新页面)",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_switch, {
                        id: "inputTr",
                        modelValue: inlineTranslate.value,
                        "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => inlineTranslate.value = $event),
                        onChange: changeInlineTranslate,
                        size: "large"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "追加AI大模型翻译",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createVNode(_component_el_switch, {
                        id: "addLLMTr",
                        modelValue: aiLabel.value,
                        "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => aiLabel.value = $event),
                        onChange: changeAiLabel,
                        size: "large"
                      }, null, 8, ["modelValue"])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "图片翻译&音频翻译(实验性功能)",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createBaseVNode("div", _hoisted_11, [
                        _hoisted_12,
                        createBaseVNode("div", _hoisted_13, [
                          createVNode(_component_el_button, {
                            id: "imgTr",
                            onClick: closeImgTr
                          }, {
                            default: withCtx(() => [
                              createTextVNode("关闭图片或音频翻译服务")
                            ]),
                            _: 1
                          })
                        ])
                      ])
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "字幕翻译支持网站",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      _hoisted_14
                    ]),
                    _: 1
                  }),
                  createVNode(_component_el_form_item, {
                    label: "快捷键",
                    class: "custom-form-item"
                  }, {
                    default: withCtx(() => [
                      createBaseVNode("div", _hoisted_15, [
                        createBaseVNode("div", _hoisted_16, [
                          (openBlock(true), createElementBlock(Fragment, null, renderList(command.value, (i) => {
                            return openBlock(), createElementBlock("p", _hoisted_17, toDisplayString(`${i.description}: ${i.shortcut}`), 1);
                          }), 256))
                        ]),
                        createBaseVNode("div", _hoisted_18, [
                          createVNode(_component_el_button, {
                            id: "imgTr",
                            onClick: goSetting
                          }, {
                            default: withCtx(() => [
                              createTextVNode("去设置快捷键")
                            ]),
                            _: 1
                          })
                        ])
                      ])
                    ]),
                    _: 1
                  })
                ]),
                _: 1
              })
            ]),
            help: withCtx(() => [
              _hoisted_19
            ]),
            _: 1
          })
        ])
      ]);
    };
  }
});
const App_vue_vue_type_style_index_0_scoped_aa470d26_lang = "";
const App_vue_vue_type_style_index_1_lang = "";
const App = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-aa470d26"]]);
const style = "";
const app = createApp(App);
app.use(installer);
app.mount("#app");
