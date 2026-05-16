import "./modulepreload-polyfill-7faf532e.js";
import "./str.ts-d3a40573.js";
import { d as defineComponent, r as ref, g as resolveComponent, h as resolveDirective, a as openBlock, c as createElementBlock, b as createBaseVNode, i as createBlock, w as withCtx, j as createCommentVNode, t as toDisplayString, k as withDirectives, F as Fragment, l as renderList, m as createVNode, e as createTextVNode, p as pushScopeId, n as popScopeId, _ as _export_sfc, f as createApp } from "./_plugin-vue_export-helper-2f49cf34.js";
import { E as ElMessage, i as installer } from "./index-dd0066b9.js";
import { b as browserPolyfillExports } from "./browser-polyfill-1bf53692.js";
import { s as setOffscreen, p as prefetchModel, y as youdao } from "./service-ba894d8a.js";
import "./index-4c0d8093.js";
import { b as browserExports } from "./shim-5b326084.js";
import { t as track } from "./common-54d607d2.js";
import "./_commonjsHelpers-7a77ea84.js";
const _withScopeId = (n) => (pushScopeId("data-v-9198a2a0"), n = n(), popScopeId(), n);
const _hoisted_1 = { class: "container" };
const _hoisted_2 = { class: "main" };
const _hoisted_3 = {
  key: 0,
  class: "upload"
};
const _hoisted_4 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("i", { class: "el-icon-upload" }, null, -1));
const _hoisted_5 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("div", { class: "el-upload__text" }, [
  /* @__PURE__ */ createTextVNode("将文件拖到此处，或"),
  /* @__PURE__ */ createBaseVNode("em", null, "点击上传英文音频"),
  /* @__PURE__ */ createTextVNode("即可开始生成字幕")
], -1));
const _hoisted_6 = /* @__PURE__ */ _withScopeId(() => /* @__PURE__ */ createBaseVNode("div", {
  class: "el-upload__tip",
  slot: "tip"
}, "仅支持英文音频上传", -1));
const _hoisted_7 = {
  key: 1,
  class: "player"
};
const _hoisted_8 = { class: "subtitleBox" };
const _hoisted_9 = { class: "orignal" };
const _hoisted_10 = {
  key: 0,
  class: "translation"
};
const _hoisted_11 = ["src"];
const _hoisted_12 = { class: "subtitle" };
const _hoisted_13 = ["element-loading-text"];
const _hoisted_14 = ["id", "onClick"];
const _hoisted_15 = { class: "time" };
const _hoisted_16 = { class: "start" };
const _hoisted_17 = { class: "end" };
const _hoisted_18 = { class: "text" };
const _hoisted_19 = { class: "orignal" };
const _hoisted_20 = ["onInput"];
const _hoisted_21 = { class: "bar" };
const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "App",
  setup(__props) {
    const stop = ref(false);
    const audioElement = ref(null);
    const substribe = ref(false);
    const uploaded = ref(false);
    const audioSrc = ref("");
    const subtitles = ref([]);
    const currentText = ref("");
    const currentTr = ref("");
    const original = ref(true);
    const translated = ref(false);
    const subtitlesLoading = ref(false);
    const subtitlesLoadingText = ref("正在解码音频");
    const updateTranslation = (event, subtitleItem) => {
      subtitleItem.tr = event.target.innerText;
    };
    const toOriginal = () => {
      original.value = !original.value;
      try {
        track(window, "toOriginal", {
          original: original.value
        });
      } catch (error) {
        console.error(error);
      }
    };
    function downloadSRT(captions) {
      try {
        track(window, "downloadSRT", {});
      } catch (error) {
        console.error(error);
      }
      const formatTime = (time) => {
        const pad = (num, size) => ("000" + num).slice(size * -1);
        let ms = time % 1;
        time = time - ms | 0;
        let seconds = time % 60;
        time = (time - seconds) / 60;
        let minutes = time % 60;
        let hours = (time - minutes) / 60;
        return `${pad(hours, 2)}:${pad(minutes, 2)}:${pad(seconds, 2)},${pad(Math.round(ms * 1e3), 3)}`;
      };
      const formatCaption = (caption, index) => {
        return `${index + 1}
${formatTime(caption.start)} --> ${formatTime(caption.end)}
${caption.text}`;
      };
      const formatCaptionTr = (caption, index) => {
        return `${index + 1}
${formatTime(caption.start)} --> ${formatTime(caption.end)}
${caption.tr}`;
      };
      let srtContent = "";
      if (original.value) {
        srtContent = captions.map(formatCaption).join("\n\n");
      } else {
        srtContent = captions.map((x, i) => {
          return `${formatCaption(x, i)}

${formatCaptionTr(x, i)}`;
        }).join("\n\n");
      }
      const blob = new Blob([srtContent], { type: "text/plain;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = "captions.srt";
      link.style.display = "none";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    }
    const downloadStr = () => {
      downloadSRT(subtitles.value.map((x) => {
        return {
          text: x.text,
          end: x.absEnd,
          start: x.absStart,
          tr: x.tr
        };
      }));
    };
    const addAsrJob = async (data) => {
      const result = await browserPolyfillExports.runtime.sendMessage({
        action: "asr",
        data
      });
      return result;
    };
    const mouseenter = () => {
      stop.value = true;
    };
    const mouseleave = () => {
      stop.value = false;
    };
    const beforeAudioUpload = (file) => {
      const isAudio = file.type.startsWith("audio/");
      if (!isAudio) {
        ElMessage.error("上传的不是音频文件!");
      }
      return isAudio;
    };
    function parseTranscript(transcript) {
      const regex = /<\|(\d+\.\d+)\|>([\s\S]*?)(<\|(\d+\.\d+)\|>|$)/g;
      const segments = [];
      let match;
      while ((match = regex.exec(transcript)) !== null) {
        const start = parseFloat(match[1]);
        const text = match[2].trim();
        const end = match[4] ? parseFloat(match[4]) : void 0;
        segments.push({
          start,
          end,
          text
        });
      }
      return segments;
    }
    const setPlayTime = (timeInSeconds) => {
      const audio = audioElement.value;
      if (audio && !isNaN(audio.duration)) {
        audio.currentTime = timeInSeconds;
      }
    };
    function secondsToHMS(seconds) {
      seconds = Math.floor(seconds);
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor(seconds % 3600 / 60);
      const sec = seconds % 60;
      const formattedHours = hours.toString().padStart(2, "0");
      const formattedMinutes = minutes.toString().padStart(2, "0");
      const formattedSeconds = sec.toString().padStart(2, "0");
      return `${formattedHours}:${formattedMinutes}:${formattedSeconds}`;
    }
    function mergeSubtitles(subtitles2) {
      const mergedSubtitles = [];
      let currentSubtitle = null;
      subtitles2.forEach((subtitle, index) => {
        if (!currentSubtitle || /[.?!]$/.test(currentSubtitle.text)) {
          currentSubtitle = { ...subtitle };
          mergedSubtitles.push(currentSubtitle);
        } else {
          currentSubtitle.text += " " + subtitle.text;
          currentSubtitle.end = subtitle.end;
          currentSubtitle.absEnd = subtitle.absEnd;
        }
      });
      return mergedSubtitles;
    }
    let lastsecond = 0;
    const process_audio = async (audio, starttime, idx, pos) => {
      if (idx > audio.length) {
        substribe.value = true;
        console.info("转录完成");
        return 0;
      }
      const kSampleRate = 16e3;
      const kSteps = kSampleRate * 30;
      const kDelay = 400;
      try {
        const xa = audio.slice(idx, idx + kSteps);
        console.log("start", (/* @__PURE__ */ new Date()).toTimeString());
        const start = performance.now();
        let transciprt = [];
        try {
          const ret = await addAsrJob(xa);
          const end = performance.now();
          const diff = end - start;
          console.log("diff", diff, start, end);
          transciprt = parseTranscript(ret.str.data[0]);
        } catch (error) {
          console.error(error);
        }
        const betterTranscript = transciprt.filter((x) => x.end).map((x) => {
          return {
            ...x,
            absStart: lastsecond + x.start,
            absEnd: lastsecond + x.end
          };
        });
        const merged = mergeSubtitles(betterTranscript);
        console.log("betterTranscript", betterTranscript);
        console.log("merged", merged);
        let translateJobs = merged.map(async (x) => {
          let tr = "翻译失败";
          try {
            tr = await youdao(x.text);
          } catch (error) {
            console.error(error);
          }
          return {
            ...x,
            tr
          };
        });
        let result = await Promise.all(translateJobs);
        subtitles.value.push(...result);
        browserExports.nextTick(() => {
          subtitlesLoading.value = false;
          translated.value = true;
        });
        setTimeout(() => {
          if (transciprt.at(-1).end) {
            process_audio(audio, starttime, idx + kSteps, pos + 30);
            lastsecond += 30;
          } else {
            process_audio(audio, starttime, idx + Math.floor(kSteps * (transciprt.at(-1).start / 30)), pos + 30);
            lastsecond += transciprt.at(-1).start;
          }
        }, kDelay);
      } catch (e) {
        console.error(e);
      }
    };
    function findInterval(arr, num) {
      let low = 0;
      let high = arr.length - 1;
      while (low <= high) {
        let mid = Math.floor((low + high) / 2);
        let [start, end] = arr[mid];
        if (num >= start && num <= end) {
          return mid;
        } else if (num < start) {
          high = mid - 1;
        } else {
          low = mid + 1;
        }
      }
      return -1;
    }
    const handleAudioUpload = async (file) => {
      let check = await setOffscreen(true);
      subtitlesLoading.value = true;
      try {
        track(window, "audioTr", {});
      } catch (error) {
        console.error(error);
      }
      if (check) {
        try {
          subtitlesLoadingText.value = "首次下载资源比较慢，请耐心等待⌛️";
          await Promise.all([prefetchModel("asr")]);
          subtitlesLoadingText.value = "下载资源成功⌛️";
          subtitlesLoadingText.value = "开始解码音频";
          audioSrc.value = URL.createObjectURL(file.file);
          uploaded.value = true;
          const context = new AudioContext({
            sampleRate: 16e3,
            channelCount: 1,
            echoCancellation: false,
            autoGainControl: true,
            noiseSuppression: true
          });
          const buffer = await (await fetch(audioSrc.value)).arrayBuffer();
          const audioBuffer = await context.decodeAudioData(buffer);
          var offlineContext = new OfflineAudioContext(audioBuffer.numberOfChannels, audioBuffer.length, audioBuffer.sampleRate);
          var source = offlineContext.createBufferSource();
          source.buffer = audioBuffer;
          source.connect(offlineContext.destination);
          source.start();
          const renderedBuffer = await offlineContext.startRendering();
          const audio = renderedBuffer.getChannelData(0);
          subtitlesLoadingText.value = "解码音频完成，进行转录";
          audioElement.value.addEventListener("timeupdate", function() {
            var audioElement2 = this;
            var duration = audioElement2.duration;
            var currentTime = audioElement2.currentTime;
            let index = findInterval(subtitles.value.map((x) => [x.absStart, x.absEnd]), currentTime);
            try {
              const i = subtitles.value.at(index);
              currentText.value = i.text;
              currentTr.value = i.tr;
            } catch (error) {
              console.error(error);
            }
            if (index !== -1 && !stop.value) {
              document.getElementById(`sub-${index}`).scrollIntoView({
                behavior: "smooth",
                // 平滑滚动
                block: "start",
                // 元素底部对齐到可视区域
                inline: "nearest"
                // 水平方向滚动最小距离
              });
            }
            console.info("index", index, subtitles.value[index]);
          });
          original.value = true;
          process_audio(audio, performance.now(), 0, 0);
        } catch (error) {
          track(window, "audioError", {
            message: 1,
            content: error.message
          });
        }
      } else {
        subtitlesLoadingText.value = "浏览器版本过旧，无法使用本功能，请升级最新的Chrome或者edge";
        track(window, "audioError", {
          message: 2
        });
      }
      return Promise.resolve();
    };
    return (_ctx, _cache) => {
      const _component_el_upload = resolveComponent("el-upload");
      const _component_el_button = resolveComponent("el-button");
      const _directive_loading = resolveDirective("loading");
      return openBlock(), createElementBlock("div", _hoisted_1, [
        createBaseVNode("div", _hoisted_2, [
          !uploaded.value ? (openBlock(), createElementBlock("div", _hoisted_3, [
            !uploaded.value ? (openBlock(), createBlock(_component_el_upload, {
              key: 0,
              "http-request": handleAudioUpload,
              drag: "",
              "before-upload": beforeAudioUpload
            }, {
              default: withCtx(() => [
                _hoisted_4,
                _hoisted_5,
                _hoisted_6
              ]),
              _: 1
            })) : createCommentVNode("", true)
          ])) : (openBlock(), createElementBlock("div", _hoisted_7, [
            createBaseVNode("div", _hoisted_8, [
              createBaseVNode("div", _hoisted_9, toDisplayString(currentText.value), 1),
              currentTr.value && !original.value ? (openBlock(), createElementBlock("div", _hoisted_10, toDisplayString(currentTr.value), 1)) : createCommentVNode("", true)
            ]),
            createBaseVNode("audio", {
              src: audioSrc.value,
              ref_key: "audioElement",
              ref: audioElement,
              controls: ""
            }, null, 8, _hoisted_11)
          ]))
        ]),
        createBaseVNode("div", _hoisted_12, [
          withDirectives((openBlock(), createElementBlock("div", {
            class: "subtitleContent",
            "element-loading-text": subtitlesLoadingText.value,
            onMouseenter: mouseenter,
            onMouseleave: mouseleave
          }, [
            (openBlock(true), createElementBlock(Fragment, null, renderList(subtitles.value, (i, k) => {
              return openBlock(), createElementBlock("div", {
                class: "subtitleItem",
                id: `sub-${k}`,
                key: i.absStart,
                onClick: ($event) => setPlayTime(i.absStart)
              }, [
                createBaseVNode("div", _hoisted_15, [
                  createBaseVNode("div", _hoisted_16, toDisplayString(secondsToHMS(i.absStart)), 1),
                  createBaseVNode("div", _hoisted_17, toDisplayString(secondsToHMS(i.absEnd)), 1)
                ]),
                createBaseVNode("div", _hoisted_18, [
                  createBaseVNode("div", _hoisted_19, toDisplayString(i.text), 1),
                  i.tr && !original.value ? (openBlock(), createElementBlock("div", {
                    key: 0,
                    class: "translation",
                    contenteditable: "true",
                    onInput: ($event) => updateTranslation($event, i)
                  }, toDisplayString(i.tr), 41, _hoisted_20)) : createCommentVNode("", true)
                ])
              ], 8, _hoisted_14);
            }), 128))
          ], 40, _hoisted_13)), [
            [_directive_loading, subtitlesLoading.value]
          ]),
          createBaseVNode("div", _hoisted_21, [
            translated.value ? (openBlock(), createBlock(_component_el_button, {
              key: 0,
              onClick: toOriginal,
              type: "primary"
            }, {
              default: withCtx(() => [
                createTextVNode(toDisplayString(!original.value ? "原文" : "译文"), 1)
              ]),
              _: 1
            })) : createCommentVNode("", true),
            createVNode(_component_el_button, {
              disabled: !substribe.value,
              onClick: downloadStr,
              type: "primary"
            }, {
              default: withCtx(() => [
                createTextVNode("下载字幕")
              ]),
              _: 1
            }, 8, ["disabled"])
          ])
        ])
      ]);
    };
  }
});
const App_vue_vue_type_style_index_0_scoped_9198a2a0_lang = "";
const App = /* @__PURE__ */ _export_sfc(_sfc_main, [["__scopeId", "data-v-9198a2a0"]]);
const style = "";
const app = createApp(App);
app.use(installer);
app.mount("#app");
