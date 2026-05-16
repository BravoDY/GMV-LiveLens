import "./modulepreload-polyfill-7faf532e.js";
import { y as useCssVars, _ as _export_sfc, a as openBlock, c as createElementBlock, b as createBaseVNode, e as createTextVNode, t as toDisplayString, q as normalizeClass, F as Fragment, l as renderList, p as pushScopeId, n as popScopeId, d as defineComponent, r as ref, x as computed, v as watchEffect, o as onMounted, g as resolveComponent, u as unref, m as createVNode, w as withCtx, k as withDirectives, z as vModelCheckbox, j as createCommentVNode, f as createApp } from "./_plugin-vue_export-helper-2f49cf34.js";
import { i as installer } from "./index-dd0066b9.js";
import { b as browserPolyfillExports } from "./browser-polyfill-1bf53692.js";
import { c as getRootDomain, i as isForbiddenUrl, d as trackWithAciveTab, e as betterOpen, f as getExtensionUrl, g as getUserConfig, u as updateUserConfig } from "./common-54d607d2.js";
import { a as shouldUpdate } from "./service-ba894d8a.js";
import { l as logoPath, b as brandPath } from "./config-b5aec82c.js";
import { R as Rule } from "./rules-c8e496f6.js";
import { r as retry } from "./index-87a14884.js";
import "./shim-5b326084.js";
import "./_commonjsHelpers-7a77ea84.js";
const style = "";
const __default__$1 = {
  props: {
    options: {
      type: Array,
      default: () => []
    },
    modelValue: {
      type: [String, Number],
      default: ""
    },
    disbale: {
      type: Boolean,
      default: false
    },
    label: String
  },
  data() {
    return {
      arrowPath: "",
      iconPath: "",
      disableIconPath: ""
    };
  },
  mounted() {
    const path = browserPolyfillExports.runtime.getURL("arrow.svg");
    this.arrowPath = `url('${path}')`;
    this.iconPath = browserPolyfillExports.runtime.getURL("school.svg");
    this.disableIconPath = browserPolyfillExports.runtime.getURL("school-g.svg");
  },
  methods: {
    changeModelValue(e) {
      this.$emit("selectedValue", e.target.value);
      this.$emit("update:modelValue", e.target.value);
    }
  }
};
const __injectCSSVars__$1 = () => {
  useCssVars((_ctx) => ({
    "bfbc6328": _ctx.arrowPath
  }));
};
const __setup__$1 = __default__$1.setup;
__default__$1.setup = __setup__$1 ? (props, ctx) => {
  __injectCSSVars__$1();
  return __setup__$1(props, ctx);
} : __injectCSSVars__$1;
const Select_vue_vue_type_style_index_0_scoped_b39297ae_lang = "";
const _hoisted_1$2 = { class: "select-container" };
const _hoisted_2$2 = ["src"];
const _hoisted_3$2 = ["value", "disabled"];
const _hoisted_4$2 = ["value"];
function _sfc_render$1(_ctx, _cache, $props, $setup, $data, $options) {
  return openBlock(), createElementBlock("div", _hoisted_1$2, [
    createBaseVNode("label", {
      class: normalizeClass([{
        selectLabel: !$props.disbale,
        disabledSelectLabel: $props.disbale
      }, "select-label"])
    }, [
      createBaseVNode("img", {
        class: "settingIcon",
        src: $props.disbale ? $data.disableIconPath : $data.iconPath
      }, null, 8, _hoisted_2$2),
      createTextVNode(toDisplayString($props.label), 1)
    ], 2),
    createBaseVNode("select", {
      class: "select-input",
      value: $props.modelValue,
      onChange: _cache[0] || (_cache[0] = (...args) => $options.changeModelValue && $options.changeModelValue(...args)),
      disabled: $props.disbale
    }, [
      (openBlock(true), createElementBlock(Fragment, null, renderList($props.options, (option) => {
        return openBlock(), createElementBlock("option", {
          key: option.value,
          value: option.value
        }, toDisplayString(option.text), 9, _hoisted_4$2);
      }), 128))
    ], 40, _hoisted_3$2)
  ]);
}
const Select = /* @__PURE__ */ _export_sfc(__default__$1, [["render", _sfc_render$1], ["__scopeId", "data-v-b39297ae"]]);
const __default__ = {
  props: {
    options: {
      type: Array,
      default: () => []
    },
    modelValue: {
      type: [String, Number],
      default: ""
    },
    disbale: {
      type: Boolean,
      default: false
    },
    label: String
  },
  data() {
    return {
      arrowPath: "",
      iconPath: "",
      disableIconPath: ""
    };
  },
  mounted() {
    const path = browserPolyfillExports.runtime.getURL("arrow.svg");
    this.arrowPath = `url('${path}')`;
    this.iconPath = browserPolyfillExports.runtime.getURL("more.svg");
  },
  methods: {
    changeModelValue(e) {
      this.$emit("selectedValue", e.target.value);
      this.$emit("update:modelValue", e.target.value);
    },
    openSelect() {
      const dropdown = this.$refs.containter;
      const event = new MouseEvent("click");
      dropdown.dispatchEvent(event);
    }
  }
};
const __injectCSSVars__ = () => {
  useCssVars((_ctx) => ({
    "3f07ce43": _ctx.arrowPath
  }));
};
const __setup__ = __default__.setup;
__default__.setup = __setup__ ? (props, ctx) => {
  __injectCSSVars__();
  return __setup__(props, ctx);
} : __injectCSSVars__;
const More_vue_vue_type_style_index_0_scoped_333c6fb7_lang = "";
const _withScopeId$1 = (n) => (pushScopeId("data-v-333c6fb7"), n = n(), popScopeId(), n);
const _hoisted_1$1 = ["src"];
const _hoisted_2$1 = ["value", "disabled"];
const _hoisted_3$1 = ["value"];
const _hoisted_4$1 = /* @__PURE__ */ _withScopeId$1(() => /* @__PURE__ */ createBaseVNode("div", { class: "arrow" }, null, -1));
function _sfc_render(_ctx, _cache, $props, $setup, $data, $options) {
  return openBlock(), createElementBlock("div", {
    class: "select-container",
    onClick: _cache[1] || (_cache[1] = (...args) => $options.openSelect && $options.openSelect(...args))
  }, [
    createBaseVNode("label", {
      class: normalizeClass([{
        selectLabel: true
      }, "select-label"])
    }, [
      createBaseVNode("img", {
        class: "settingIcon",
        src: $data.iconPath
      }, null, 8, _hoisted_1$1),
      createTextVNode(toDisplayString($props.label), 1)
    ]),
    createBaseVNode("select", {
      class: "select-input",
      value: $props.modelValue,
      onChange: _cache[0] || (_cache[0] = (...args) => $options.changeModelValue && $options.changeModelValue(...args)),
      disabled: $props.disbale,
      ref: "containter"
    }, [
      (openBlock(true), createElementBlock(Fragment, null, renderList($props.options, (option) => {
        return openBlock(), createElementBlock("option", {
          key: option.value,
          value: option.value
        }, toDisplayString(option.text), 9, _hoisted_3$1);
      }), 128))
    ], 40, _hoisted_2$1),
    _hoisted_4$1
  ]);
}
const More = /* @__PURE__ */ _export_sfc(__default__, [["render", _sfc_render], ["__scopeId", "data-v-333c6fb7"]]);
const _withScopeId = (n) => (pushScopeId("data-v-9b31eaea"), n = n(), popScopeId(), n);
const _hoisted_1 = { class: "container" };
const _hoisted_2 = { class: "header" };
const _hoisted_3 = { class: "brand" };
const _hoisted_4 = { class: "icon" };
const _hoisted_5 = ["src"];
const _hoisted_6 = { class: "text" };
const _hoisted_7 = ["src"];
const _hoisted_8 = { class: "setting" };
const _hoisted_9 = ["src"];
const _hoisted_10 = { class: "main" };
const _hoisted_11 = { class: "checkboxContainer" };
const _hoisted_12 = { class: "checkbox-container" };
const _hoisted_13 = ["disabled"];
const _hoisted_14 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("label", { for: "website" }, "总是翻译该网站", -1));
const _hoisted_15 = {
  class: "checkbox-container",
  style: { "margin-top": "16px" }
};
const _hoisted_16 = ["disabled"];
const _hoisted_17 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("label", { for: "inputbox" }, "输入框翻译", -1));
const _hoisted_18 = {
  class: "checkbox-container",
  style: { "margin-top": "16px" }
};
const _hoisted_19 = ["disabled"];
const _hoisted_20 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("label", { for: "orignal" }, "仅译文(实验特性)", -1));
const _hoisted_21 = {
  key: 0,
  class: "checkbox-container",
  style: { "margin-top": "16px" }
};
const _hoisted_22 = ["disabled"];
const _hoisted_23 = { for: "subtitles" };
const _hoisted_24 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("hr", { class: "divider" }, null, -1));
const _hoisted_25 = { class: "footer" };
const _hoisted_26 = { class: "version" };
const _hoisted_27 = {
  key: 0,
  class: "message"
};
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "App",
  setup(__props) {
    useCssVars((_ctx) => ({
      "384bd7ff": label.value
    }));
    const domain = ref(0);
    const domainOption = computed(() => {
      return [
        { value: 0, text: "通用场景" },
        { value: 1, text: `计算机` },
        { value: 2, text: `医学` },
        { value: 3, text: `金融经济` }
      ];
    });
    const menu = ref(0);
    const memuOption = computed(() => {
      return [
        { value: "0", text: "" },
        { value: "5", text: "📢 音频翻译" },
        { value: "1", text: "📜 文档翻译" },
        { value: "2", text: "📄 arxivPDF论文翻译" },
        { value: "3", text: "💬 功能反馈" },
        { value: "4", text: "😘 评论支持" },
        { value: "6", text: "💡 帮助文档" }
      ];
    });
    const forbidden = ref(false);
    const translated = ref(false);
    const selectedApi = ref("youdao");
    const label = computed(() => {
      return selectedApi.value === "youdao" ? "block" : "none";
    });
    const isUnhealth = ref(false);
    const curentTabUrl = ref("");
    const strategy = ref(false);
    const inputStrategy = ref(false);
    const mode = ref(false);
    const subtitle = ref(false);
    ref(false);
    const infoNow = ref(false);
    const message = ref("");
    const quizUrl = ref("");
    const buttomText = ref("");
    const isLLM = computed(() => {
      return selectedApi.value === "youdaollm";
    });
    const changeMemu = async (menu2) => {
      if (menu2 === "1") {
        await browserPolyfillExports.runtime.sendMessage({ action: "openNewTab", url: `https://fanyi.youdao.com/index.html#/documentUpload` });
      } else if (menu2 === "2") {
        await browserPolyfillExports.runtime.sendMessage({ action: "openNewTab", url: `https://fanyi.youdao.com/trans/#/home` });
      } else if (menu2 === "3") {
        await quiz();
      } else if (menu2 === "4") {
        const channel = "EDGE";
        const sites = {
          CHROME: "https://chromewebstore.google.com/detail/%E6%9C%89%E9%81%93%E7%81%B5%E5%8A%A8%E7%BF%BB%E8%AF%91/jlpcnoohcpfgpbalhlggdhjocgnlgafn",
          EDGE: "https://microsoftedge.microsoft.com/addons/detail/%E6%9C%89%E9%81%93%E7%81%B5%E5%8A%A8%E7%BF%BB%E8%AF%91/memhacajcfhmibggbgilihlmiiddeggo",
          ZIP: "https://microsoftedge.microsoft.com/addons/detail/%E6%9C%89%E9%81%93%E7%81%B5%E5%8A%A8%E7%BF%BB%E8%AF%91/memhacajcfhmibggbgilihlmiiddeggo"
        };
        await browserPolyfillExports.runtime.sendMessage({ action: "openNewTab", url: sites[channel] });
      } else if (menu2 === "5") {
        await studio();
      } else if (menu2 === "6") {
        await help();
      }
      window.close();
    };
    const imageHelp = async () => {
      try {
        await trackWithAciveTab("imageHelp", {});
      } catch (error) {
        console.error(error);
      }
      const website = "https://magicfanyi.youdao.com/#/image";
      await browserPolyfillExports.runtime.sendMessage({ action: "openNewTab", url: website });
    };
    const getCurrentFooterText = async () => {
      if (isUnhealth.value) {
        return forbidden.value ? "当前网站无法使用插件" : "请等待页面加载完毕";
      } else if (infoNow.value) {
        const config = await getUserConfig();
        return config.config.warning;
      }
      return "";
    };
    async function getAltKeyText() {
      var _a;
      const commands = await browserPolyfillExports.commands.getAll();
      console.log("commands", commands);
      return (_a = commands.find((x) => x.name === "translate")) == null ? void 0 : _a.shortcut;
    }
    const getButtomText = async () => {
      if (isUnhealth.value && !forbidden.value) {
        return "等待页面加载完毕";
      }
      const keyText = await getAltKeyText();
      console.log(keyText, "keyText");
      if (translated.value) {
        return "显示原文 " + keyText;
      } else {
        return "翻译" + keyText;
      }
    };
    watchEffect(async () => {
      buttomText.value = await getButtomText();
    });
    const curentTabHost = computed(() => {
      try {
        if (curentTabUrl.value === "")
          return "";
        const host = getRootDomain(curentTabUrl.value);
        return host;
      } catch (error) {
        console.error(error);
        return "";
      }
    });
    const getVersion = () => {
      const manifestData = browserPolyfillExports.runtime.getManifest();
      return `V${manifestData.version} Beta`;
    };
    const help = async () => {
      try {
        await trackWithAciveTab("help", {});
      } catch (error) {
        console.error(error);
      }
      const website = "https://magicfanyi.youdao.com/#/help";
      await betterOpen(website);
    };
    const studio = async () => {
      try {
        await trackWithAciveTab("openStudio", {});
      } catch (error) {
        console.error(error);
      }
      await betterOpen(getExtensionUrl("src/studio/index.html"));
    };
    const apiChange = async (i) => {
      if (selectedApi.value === i) {
        return 0;
      }
      selectedApi.value = i;
      try {
        await trackWithAciveTab("apiChange", {
          strategy: i
        });
      } catch (error) {
        console.error(error);
      }
      getUserConfig().then((config) => {
        config.engine = i;
        updateUserConfig(config);
      });
      handleOriginal();
    };
    const buttonClick = () => {
      try {
        trackWithAciveTab("buttonClick", {});
      } catch (error) {
        console.error(error);
      }
      handleOriginal();
    };
    const changeStrategy = async (e) => {
      const i = e.target.checked ? 1 : 0;
      strategy.value = !!i;
      try {
        await trackWithAciveTab("changeStrategy", {
          strategy: i
        });
      } catch (error) {
        console.error(error);
      }
      const host = curentTabHost.value;
      const config = await getUserConfig();
      if (config.strategy === void 0)
        config.strategy = {};
      config.strategy[host] = i;
      await updateUserConfig(config);
    };
    const changeDomain = async () => {
      try {
        await trackWithAciveTab("changeDomain", {
          domain: domain.value
        });
      } catch (error) {
        console.error(error);
      }
      const config = await getUserConfig();
      config.domain = domain.value;
      await updateUserConfig(config);
      handleOriginal();
    };
    const changeInputStrategy = async (e) => {
      const i = e.target.checked ? 1 : 0;
      inputStrategy.value = !!i;
      try {
        await trackWithAciveTab("changeInputStrategy", {
          strategy: i
        });
      } catch (error) {
        console.error(error);
      }
      const host = curentTabHost.value;
      const config = await getUserConfig();
      if (config.inputStrategy === void 0)
        config.inputStrategy = {};
      config.inputStrategy[host] = i;
      if (+i === 1) {
        config.inlineTranslate = true;
      }
      await updateUserConfig(config);
      const tabs = await browserPolyfillExports.tabs.query({ active: true, currentWindow: true });
      await browserPolyfillExports.tabs.sendMessage(tabs[0].id, { action: "setUnlock", unlock: i });
    };
    const changeMode = async (e) => {
      const i = e.target.checked;
      mode.value = i;
      try {
        await trackWithAciveTab("changeMode", {
          isOrignal: i
        });
      } catch (error) {
        console.error(error);
      }
      const config = await getUserConfig();
      config.mode = i ? "orignal" : "dual";
      await updateUserConfig(config);
    };
    const changeSubtitle = async (e) => {
      const i = e.target.checked;
      subtitle.value = !!i;
      try {
        await trackWithAciveTab("changeSubtitles", {
          subtitles: i
        });
      } catch (error) {
        console.error(error);
      }
      const host = curentTabHost.value;
      const config = await getUserConfig();
      if (config.subtitles === void 0)
        config.subtitles = {};
      config.subtitles[host] = i;
      await updateUserConfig(config);
      try {
        const tabs = await browserPolyfillExports.tabs.query({ active: true, currentWindow: true });
        await browserPolyfillExports.tabs.sendMessage(tabs[0].id, { action: "toggleSubtilte", status: i });
        window.close();
      } catch (error) {
        console.log(error);
      }
    };
    const openOtptionPage = async () => {
      try {
        await trackWithAciveTab("openOtptionPage", {});
      } catch (error) {
        console.error(error);
      }
      await betterOpen(getExtensionUrl("src/options/index.html"));
    };
    const quiz = async () => {
      try {
        await trackWithAciveTab("quiz", {});
      } catch (error) {
        console.error(error);
      }
      const config = await getUserConfig();
      const id = config.userId;
      const url = config.config.feelback_url;
      const website = "https://magicfanyi.youdao.com/#/";
      const uninstallUrl = `${website}catch?ss=${id}&url=${url}&type=feedback`;
      await betterOpen(uninstallUrl);
    };
    const initConfig = async () => {
      const config = await getUserConfig();
      const host = curentTabHost.value;
      const strategyV = typeof config.strategy[host] === "undefined" ? false : config.strategy[host];
      strategy.value = !!strategyV;
      const inputStrategyV = config.inlineTranslate ? typeof config.inputStrategy[host] === "undefined" ? false : config.inputStrategy[host] : false;
      inputStrategy.value = !!inputStrategyV;
      const subtitleV = typeof config.subtitles[host] === "undefined" ? false : config.subtitles[host];
      subtitle.value = !!subtitleV;
      const rulesMangement = new Rule();
      const translateSettingMap = await rulesMangement.getQueueSetting();
      if (config.engine in translateSettingMap) {
        selectedApi.value = config.engine;
      } else {
        selectedApi.value = "youdao";
        const config2 = await getUserConfig();
        config2.engine = "youdao";
        await updateUserConfig(config2);
      }
      mode.value = config.mode === "orignal";
      domain.value = config.domain ?? 0;
      if (config.config.warning && config.config.warning.length > 0) {
        infoNow.value = true;
      }
      message.value = await getCurrentFooterText();
      quizUrl.value = config.config.feelback_url;
    };
    const rePing = () => {
      const op = retry.operation({
        maxRetryTime: 1e3 * 30
      });
      isUnhealth.value = true;
      return new Promise((resolve, reject) => {
        op.attempt(async (currentAttempt) => {
          try {
            const tabs = await browserPolyfillExports.tabs.query({ active: true, currentWindow: true });
            const result = await browserPolyfillExports.tabs.sendMessage(tabs[0].id, { action: "getSetting" });
            isUnhealth.value = !result.isHealth;
            translated.value = result.translated;
            resolve("All good!");
          } catch (error) {
            op.retry(error);
          }
        });
      });
    };
    const handleOriginal = async () => {
      if (isUnhealth.value)
        return;
      const op = retry.operation({
        maxRetryTime: 1e3 * 30
      });
      return new Promise((resolve, reject) => {
        op.attempt(async (currentAttempt) => {
          try {
            const tabs = await browserPolyfillExports.tabs.query({ active: true, currentWindow: true });
            const result = await browserPolyfillExports.tabs.sendMessage(tabs[0].id, { action: "toggle", api: selectedApi.value, mode: mode.value ? "orignal" : "dual", domain: domain.value });
            translated.value = result.translated;
            window.close();
            resolve("All good!");
          } catch (error) {
            op.retry(error);
          }
        });
      });
    };
    onMounted(async () => {
      await shouldUpdate(1e3 * 60 * 60 * 2);
      forbidden.value = await isForbiddenUrl();
      const tabs = await browserPolyfillExports.tabs.query({ active: true, currentWindow: true });
      curentTabUrl.value = tabs[0].url;
      initConfig();
      rePing();
    });
    return (_ctx, _cache) => {
      const _component_el_tooltip = resolveComponent("el-tooltip");
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
          ]),
          createBaseVNode("div", _hoisted_8, [
            createVNode(_component_el_tooltip, {
              effect: "dark",
              content: "设置",
              placement: "bottom"
            }, {
              default: withCtx(() => [
                createBaseVNode("img", {
                  class: "settingIcon",
                  src: unref(browserPolyfillExports).runtime.getURL("Setting.svg"),
                  style: { "margin-right": "0" },
                  onClick: openOtptionPage
                }, null, 8, _hoisted_9)
              ]),
              _: 1
            })
          ])
        ]),
        createBaseVNode("div", _hoisted_10, [
          createBaseVNode("div", {
            class: normalizeClass(`${isUnhealth.value ? "switch disable-switch" : "switch"}`)
          }, [
            createBaseVNode("div", {
              class: normalizeClass(selectedApi.value === "youdao" ? "youdao" : "youdao-nocheck"),
              onClick: _cache[0] || (_cache[0] = ($event) => apiChange("youdao"))
            }, "有道翻译", 2),
            createBaseVNode("div", {
              class: normalizeClass(selectedApi.value === "youdaollm" ? "llm" : "llm-nocheck"),
              onClick: _cache[1] || (_cache[1] = ($event) => apiChange("youdaollm"))
            }, "AI大模型翻译", 2)
          ], 2),
          createBaseVNode("div", _hoisted_11, [
            createBaseVNode("div", _hoisted_12, [
              withDirectives(createBaseVNode("input", {
                type: "checkbox",
                class: "checkbox-custom",
                id: "website",
                disabled: isUnhealth.value,
                "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => strategy.value = $event),
                onChange: changeStrategy
              }, null, 40, _hoisted_13), [
                [vModelCheckbox, strategy.value]
              ]),
              _hoisted_14
            ]),
            createBaseVNode("div", _hoisted_15, [
              withDirectives(createBaseVNode("input", {
                type: "checkbox",
                class: "checkbox-custom",
                id: "inputbox",
                disabled: isUnhealth.value,
                "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => inputStrategy.value = $event),
                onChange: changeInputStrategy
              }, null, 40, _hoisted_16), [
                [vModelCheckbox, inputStrategy.value]
              ]),
              _hoisted_17
            ]),
            createBaseVNode("div", _hoisted_18, [
              withDirectives(createBaseVNode("input", {
                type: "checkbox",
                class: "checkbox-custom",
                id: "orignal",
                disabled: isUnhealth.value,
                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => mode.value = $event),
                onChange: changeMode
              }, null, 40, _hoisted_19), [
                [vModelCheckbox, mode.value]
              ]),
              _hoisted_20
            ]),
            curentTabHost.value === "twitter.com" ? (openBlock(), createElementBlock("div", _hoisted_21, [
              withDirectives(createBaseVNode("input", {
                type: "checkbox",
                class: "checkbox-custom",
                id: "subtitles",
                disabled: isUnhealth.value,
                "onUpdate:modelValue": _cache[5] || (_cache[5] = ($event) => subtitle.value = $event),
                onChange: changeSubtitle
              }, null, 40, _hoisted_22), [
                [vModelCheckbox, subtitle.value]
              ]),
              createBaseVNode("label", _hoisted_23, toDisplayString(curentTabHost.value === "twitter.com" ? "Spaces CC字幕翻译" : "自动翻译字幕"), 1)
            ])) : createCommentVNode("", true)
          ]),
          _hoisted_24,
          createBaseVNode("div", { class: "action" }, [
            createBaseVNode("div", {
              class: "image",
              onClick: imageHelp
            }, " 🖼️ 图片翻译引导 "),
            createBaseVNode("div", {
              class: "audio",
              onClick: studio
            }, " 📢 音频翻译入口 ")
          ]),
          createVNode(Select, {
            label: "翻译策略",
            onSelectedValue: changeDomain,
            options: domainOption.value,
            modelValue: domain.value,
            "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => domain.value = $event),
            disbale: isUnhealth.value || isLLM.value
          }, null, 8, ["options", "modelValue", "disbale"]),
          createVNode(More, {
            label: "更多功能",
            onSelectedValue: changeMemu,
            options: memuOption.value,
            modelValue: menu.value,
            "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => menu.value = $event),
            disbale: isUnhealth.value
          }, null, 8, ["options", "modelValue", "disbale"]),
          createBaseVNode("button", {
            class: normalizeClass(`${isUnhealth.value ? "translate disbaled" : "translate"}`),
            onClick: buttonClick
          }, [
            createBaseVNode("span", {
              class: normalizeClass(`${isUnhealth.value ? "front disbaled" : "front"}`)
            }, toDisplayString(buttomText.value), 3)
          ], 2)
        ]),
        createBaseVNode("div", _hoisted_25, [
          createBaseVNode("div", _hoisted_26, toDisplayString(getVersion()), 1),
          isUnhealth.value || infoNow.value ? (openBlock(), createElementBlock("div", _hoisted_27, [
            createBaseVNode("div", null, toDisplayString(message.value), 1)
          ])) : createCommentVNode("", true)
        ])
      ]);
    };
  }
});
const App_vue_vue_type_style_index_0_scoped_9b31eaea_lang = "";
const App = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-9b31eaea"]]);
const app = createApp(App);
app.use(installer);
app.mount("#app");
