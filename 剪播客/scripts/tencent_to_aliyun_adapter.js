#!/usr/bin/env node
/**
 * 腾讯云 ASR → 阿里云 FunASR 格式适配器
 *
 * 将腾讯云的转录结果转换为阿里云 FunASR 兼容格式，
 * 使下游脚本（identify_speakers.js, generate_subtitles_from_aliyun.js）无需修改。
 *
 * 用法: node tencent_to_aliyun_adapter.js <tencent_result.json> [output.json]
 */

const fs = require('fs');
const path = require('path');

if (process.argv.length < 3) {
    console.error('用法: node tencent_to_aliyun_adapter.js <tencent_result.json> [output.json]');
    process.exit(1);
}

const inputFile = process.argv[2];
const outputFile = process.argv[3] || 'aliyun_funasr_transcription.json';

let tencentData;
try {
    tencentData = JSON.parse(fs.readFileSync(inputFile, 'utf8'));
} catch (e) {
    console.error(`❌ 读取失败: ${inputFile}`);
    process.exit(1);
}

// 提取腾讯云结果
const response = tencentData.Response || tencentData;
const resultData = response.Data || response;
const resultText = resultData.Result || '';
const wordList = resultData.WordList || [];
const sentenceList = resultData.SentenceList || resultData.ResultDetail || [];

// 转换为阿里云 FunASR 兼容格式
const sentences = [];
const words = [];

if (sentenceList.length > 0) {
    // 使用句子级结果
    sentenceList.forEach((sentence, idx) => {
        const speakerId = sentence.SpeakerId !== undefined ? sentence.SpeakerId : 0;
        const startMs = sentence.StartMs || sentence.StartTime || 0;
        const endMs = sentence.EndMs || sentence.EndTime || 0;
        const text = sentence.FinalSentence || sentence.Text || '';

        // 构建句子
        const sentenceObj = {
            sentence_id: idx,
            text: text,
            begin_time: startMs,
            end_time: endMs,
            speaker_id: String(speakerId),
            words: [],
        };

        // 如果有词级信息
        if (sentence.WordList) {
            sentence.WordList.forEach(word => {
                sentenceObj.words.push({
                    text: word.Word || word.Text || '',
                    begin_time: word.OffsetStartMs || word.StartTime || startMs,
                    end_time: word.OffsetEndMs || word.EndTime || endMs,
                });
            });
        } else if (sentence.Words) {
            sentence.Words.forEach(word => {
                sentenceObj.words.push({
                    text: word.Word || '',
                    begin_time: word.OffsetStartMs || startMs,
                    end_time: word.OffsetEndMs || endMs,
                });
            });
        }

        sentences.push(sentenceObj);
    });
} else if (wordList.length > 0) {
    // fallback: 从词级结果构建句子
    let currentSentence = null;
    let sentenceIdx = 0;

    wordList.forEach(word => {
        const speakerId = word.SpeakerId !== undefined ? word.SpeakerId : 0;

        if (!currentSentence || currentSentence.speaker_id !== String(speakerId)) {
            if (currentSentence) {
                sentences.push(currentSentence);
            }
            currentSentence = {
                sentence_id: sentenceIdx++,
                text: '',
                begin_time: word.OffsetStartMs || word.StartTime || 0,
                end_time: 0,
                speaker_id: String(speakerId),
                words: [],
            };
        }

        currentSentence.text += word.Word || '';
        currentSentence.end_time = word.OffsetEndMs || word.EndTime || 0;
        currentSentence.words.push({
            text: word.Word || '',
            begin_time: word.OffsetStartMs || word.StartTime || 0,
            end_time: word.OffsetEndMs || word.EndTime || 0,
        });
    });

    if (currentSentence) {
        sentences.push(currentSentence);
    }
}

// 构建阿里云 FunASR 兼容的输出格式
const aliyunFormat = {
    transcripts: [{
        sentences: sentences,
        // 元数据
        _source: 'tencent_asr_adapter',
        _original_format: 'tencent',
    }],
};

fs.writeFileSync(outputFile, JSON.stringify(aliyunFormat, null, 2), 'utf8');

// 统计
const speakers = {};
sentences.forEach(s => {
    speakers[s.speaker_id] = (speakers[s.speaker_id] || 0) + 1;
});

console.log(`📊 转换完成:`);
console.log(`   总句数: ${sentences.length}`);
console.log(`   说话人分布:`);
Object.keys(speakers).sort().forEach(spk => {
    const count = speakers[spk];
    const pct = (count / sentences.length * 100).toFixed(1);
    console.log(`     Speaker ${spk}: ${count}句 (${pct}%)`);
});
