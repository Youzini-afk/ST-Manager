/**
 * static/js/components/advancedEditor.js
 * 高级编辑器组件 (正则脚本 & 扩展脚本)
 */

import { updateShadowContent } from '../utils/dom.js';

export default function advancedEditor() {
    return {
        // === 本地状态 ===
        showAdvancedModal: false,
        activeRegexIndex: -1,
        showMobileSidebar: false, // 移动端侧边栏显示状态
        
        regexPreviewMode: 'text', // text | html
        showLargePreview: false,

        // 正则测试
        regexTestInput: "",
        regexTestResult: "",

        // 数据引用 (从 detailModal 传入)
        editingData: {
            extensions: {
                regex_scripts: [],
                tavern_helper: []
            }
        },

        updateShadowContent,

        init() {
            // 监听打开事件
            // detailModal 或者 HTML 中的按钮需要触发此事件，并传递 editingData 的引用
            window.addEventListener('open-advanced-editor', (e) => {
                this.editingData = e.detail; // 接收引用，实现响应式同步
                this.showAdvancedModal = true;
                this.activeRegexIndex = -1;
                this.regexTestInput = "";
                this.regexTestResult = "";
                this.regexPreviewMode = 'text';
                // 移动端默认关闭侧边栏
                if (this.$store.global.deviceType === 'mobile') {
                    this.showMobileSidebar = false;
                }
            });
        },

        // === Regex Script 管理 ===

        addRegexScript() {
            const newScript = {
                id: crypto.randomUUID(),
                scriptName: "新正则脚本",
                findRegex: "",
                replaceString: "",
                trimStrings: [],          // 剔除字符串数组
                placement: [2],           // 默认生效位置：2 (AI Output)
                disabled: false,
                markdownOnly: false,      // 仅影响显示
                promptOnly: false,        // 仅影响提示词
                runOnEdit: true,          // 编辑时运行
                substituteRegex: 0,       // 宏替换模式
                minDepth: null,
                maxDepth: null
            };

            // 确保结构存在
            if (!this.editingData.extensions) this.editingData.extensions = {};
            if (!this.editingData.extensions.regex_scripts) {
                this.editingData.extensions.regex_scripts = [];
            }

            this.editingData.extensions.regex_scripts.push(newScript);
            this.activeRegexIndex = this.editingData.extensions.regex_scripts.length - 1;
        },

        removeRegexScript(index) {
            if (confirm("确定删除此正则脚本？")) {
                this.editingData.extensions.regex_scripts.splice(index, 1);
                this.activeRegexIndex = -1;
            }
        },

        moveRegex(index, dir) {
            const list = this.editingData.extensions.regex_scripts;
            const newIdx = index + dir;
            if (newIdx < 0 || newIdx >= list.length) return;

            // 交换
            const temp = list[index];
            list[index] = list[newIdx];
            list[newIdx] = temp;

            // 保持选中状态跟随
            if (this.activeRegexIndex === index) this.activeRegexIndex = newIdx;
            else if (this.activeRegexIndex === newIdx) this.activeRegexIndex = index;
            
            // 强制更新数组以触发 Alpine 响应式
            this.editingData.extensions.regex_scripts = [...list];
        },

        // 处理 Placement (SillyTavern 使用整数枚举数组)
        toggleRegexPlacement(script, value) {
            const val = parseInt(value);
            if (!script.placement) script.placement = [];

            const idx = script.placement.indexOf(val);
            if (idx > -1) {
                script.placement.splice(idx, 1);
            } else {
                script.placement.push(val);
            }
        },

        // === 正则测试逻辑 ===

        runRegexTest() {
            const script = this.editingData.extensions.regex_scripts[this.activeRegexIndex];
            if (!script) return;

            if (!this.regexTestInput) {
                this.regexTestResult = "";
                return;
            }
            if (!script.findRegex) {
                this.regexTestResult = this.regexTestInput;
                return;
            }

            try {
                const flags = "g" + (script.caseSensitive ? "" : "i") + "m";
                const regex = new RegExp(script.findRegex, flags);

                let result = this.regexTestInput;

                // 1. Trim Strings (预处理剔除)
                if (script.trimStrings && Array.isArray(script.trimStrings)) {
                    script.trimStrings.forEach(trimStr => {
                        if (trimStr) result = result.split(trimStr).join("");
                    });
                }

                // 2. Replace (正则替换)
                result = result.replace(regex, script.replaceString || "");

                this.regexTestResult = result;
            } catch (e) {
                this.regexTestResult = "❌ 正则表达式错误: " + e.message;
            }
        },

        // === Trim Strings 辅助 (Textarea <-> Array) ===

        updateTrimStrings(script, text) {
            // 按换行符分割，去除空行
            script.trimStrings = text.split('\n').filter(line => line.length > 0);
        },

        getTrimStringsText(script) {
            if (Array.isArray(script.trimStrings)) {
                return script.trimStrings.join('\n');
            }
            return "";
        },

        // === Tavern Scripts (Post-History / Slash Commands) ===

        getTavernScripts() {
            if (!this.editingData.extensions) return [];
            const helper = this.editingData.extensions.tavern_helper;
            if (!Array.isArray(helper)) return [];

            // 查找 ["scripts", Array] 结构
            const scriptBlock = helper.find(item => Array.isArray(item) && item[0] === "scripts");
            return (scriptBlock && Array.isArray(scriptBlock[1])) ? scriptBlock[1] : [];
        },

        addTavernScript() {
            const newScript = {
                name: "新脚本",
                type: "script",
                content: "$(()=>{\n\n});",
                enabled: false,
                id: crypto.randomUUID()
            };

            // 确保 extensions 结构
            if (!this.editingData.extensions) this.editingData.extensions = {};
            let helper = this.editingData.extensions.tavern_helper;
            
            if (!Array.isArray(helper)) {
                helper = [];
                this.editingData.extensions.tavern_helper = helper;
            }

            // 查找 scripts 块
            let scriptBlock = helper.find(item => Array.isArray(item) && item[0] === "scripts");

            // 如果没有，初始化标准结构
            if (!scriptBlock) {
                scriptBlock = ["scripts", []];
                helper.push(scriptBlock);
                // 补齐 variables 块保持规范
                if (!helper.find(item => Array.isArray(item) && item[0] === "variables")) {
                    helper.push(["variables", {}]);
                }
            }

            scriptBlock[1].push(newScript);
            
            // 强制更新
            this.editingData.extensions.tavern_helper = [...helper];
        },

        removeTavernScript(scriptId) {
            const helper = this.editingData.extensions.tavern_helper;
            const scriptBlock = helper.find(item => Array.isArray(item) && item[0] === "scripts");
            if (scriptBlock) {
                scriptBlock[1] = scriptBlock[1].filter(s => s.id !== scriptId);
                // 强制更新
                this.editingData.extensions.tavern_helper = [...helper];
            }
        },

        moveTavernScript(scriptId, dir) {
            const helper = this.editingData.extensions.tavern_helper;
            const scriptBlock = helper.find(item => Array.isArray(item) && item[0] === "scripts");
            if (!scriptBlock || !Array.isArray(scriptBlock[1])) return;

            const list = scriptBlock[1];
            const index = list.findIndex(s => s.id === scriptId);
            if (index === -1) return;

            const newIdx = index + dir;
            if (newIdx < 0 || newIdx >= list.length) return;

            // 交换
            const temp = list[index];
            list[index] = list[newIdx];
            list[newIdx] = temp;

            // 强制更新
            this.editingData.extensions.tavern_helper = [...helper];
        }
    }
}