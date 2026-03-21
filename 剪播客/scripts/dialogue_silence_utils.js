#!/usr/bin/env node
/**
 * 对话感知静音处理 — 共享工具模块
 *
 * 被 run_fine_analysis.js 和 merge_llm_fine.js 共同引用，
 * 确保两层使用完全一致的阈值和压缩逻辑。
 *
 * 用法:
 *   const { buildSpeakerBaselines, getAdaptiveThreshold, computeKeepDuration } = require('./dialogue_silence_utils');
 */

/**
 * 在 allWords 中查找 gap 前后的说话人
 * @param {Array} allWords - 完整词列表
 * @param {number} gapIdx - gap 在 allWords 中的索引
 * @returns {{ prevSpeaker: string|null, nextSpeaker: string|null }}
 */
function findGapSpeakers(allWords, gapIdx) {
  let prevSpeaker = null, nextSpeaker = null;
  for (let i = gapIdx - 1; i >= 0; i--) {
    if (allWords[i].speaker && !allWords[i].isSpeakerLabel && !allWords[i].isGap) {
      prevSpeaker = allWords[i].speaker;
      break;
    }
  }
  for (let i = gapIdx + 1; i < allWords.length; i++) {
    if (allWords[i].speaker && !allWords[i].isSpeakerLabel && !allWords[i].isGap) {
      nextSpeaker = allWords[i].speaker;
      break;
    }
  }
  return { prevSpeaker, nextSpeaker };
}

/**
 * 计算数组中位数
 */
function median(arr) {
  if (!arr.length) return 0.5;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/**
 * 构建每个说话人的节奏基线（同人 gap 中位数）
 * @param {Array} allWords - 完整词列表
 * @returns {{ speakerMedian: Object, globalMedian: number, isDialogue: boolean, speakerSampleCounts: Object }}
 */
function buildSpeakerBaselines(allWords) {
  const speakerGapDurations = {};
  for (let i = 0; i < allWords.length; i++) {
    if (!allWords[i].isGap) continue;
    const dur = allWords[i].end - allWords[i].start;
    if (dur < 0.1) continue;
    const { prevSpeaker, nextSpeaker } = findGapSpeakers(allWords, i);
    if (prevSpeaker && prevSpeaker === nextSpeaker) {
      if (!speakerGapDurations[prevSpeaker]) speakerGapDurations[prevSpeaker] = [];
      speakerGapDurations[prevSpeaker].push(dur);
    }
  }

  const speakerMedian = {};
  const allSpeakerGaps = [];
  const speakerSampleCounts = {};
  for (const [speaker, durs] of Object.entries(speakerGapDurations)) {
    speakerMedian[speaker] = median(durs);
    speakerSampleCounts[speaker] = durs.length;
    allSpeakerGaps.push(...durs);
  }
  const globalMedian = allSpeakerGaps.length ? median(allSpeakerGaps) : 0.5;
  const isDialogue = Object.keys(speakerMedian).length >= 2;

  return { speakerMedian, globalMedian, isDialogue, speakerSampleCounts };
}

/**
 * 根据上下文计算自适应阈值和保留上限
 * @param {number} baseMedian - 说话人基线中位数
 * @param {string} context - 'after-question' | 'cross-speaker' | 'same-speaker'
 * @returns {{ threshold: number, keepCeiling: number }}
 */
function getAdaptiveThreshold(baseMedian, context) {
  switch (context) {
    case 'after-question':
      return {
        threshold: Math.min(Math.max(baseMedian * 3, 1.5), 2.5),
        keepCeiling: 1.5,
      };
    case 'cross-speaker':
      return {
        threshold: Math.min(Math.max(baseMedian * 2.5, 1.2), 2.0),
        keepCeiling: 1.3,
      };
    case 'same-speaker':
    default:
      return {
        threshold: Math.min(Math.max(baseMedian * 2, 0.8), 1.5),
        keepCeiling: 1.0,
      };
  }
}

/**
 * 计算压缩后保留时长
 * @param {number} duration - 原始 gap 时长
 * @param {number} threshold - 自适应阈值
 * @param {number} keepCeiling - 保留上限
 * @returns {number} 保留时长
 */
function computeKeepDuration(duration, threshold, keepCeiling) {
  const keepFloor = 0.4;
  const keepBase = threshold * 0.5;
  const keepExcess = (duration - threshold) * 0.3;
  return Math.max(keepFloor, Math.min(keepCeiling, keepBase + keepExcess));
}

/**
 * 判断上下文类型
 * @param {boolean} isDialogue - 是否多人对话
 * @param {string|null} prevSpeaker
 * @param {string|null} nextSpeaker
 * @param {boolean} afterQuestion - 是否在问句之后
 * @returns {string} 'after-question' | 'cross-speaker' | 'same-speaker'
 */
function classifyContext(isDialogue, prevSpeaker, nextSpeaker, afterQuestion) {
  if (afterQuestion) return 'after-question';
  if (isDialogue && prevSpeaker && nextSpeaker && prevSpeaker !== nextSpeaker) return 'cross-speaker';
  return 'same-speaker';
}

module.exports = {
  findGapSpeakers,
  median,
  buildSpeakerBaselines,
  getAdaptiveThreshold,
  computeKeepDuration,
  classifyContext,
};
