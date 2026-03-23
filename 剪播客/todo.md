# 播客剪辑 TODO

## 架构改进

- [ ] **精剪引入 LLM 二次确认**：当前精剪（Step 5b）纯 pattern matching，缺乏语义理解，导致数字（100→"0""0"）、特殊表达等误判。方案：pattern matching 先出候选，LLM 判断 true/false，保留精确时间戳定位能力。优先级：中。触发场景：新 podcast 出现新类型误判时。
