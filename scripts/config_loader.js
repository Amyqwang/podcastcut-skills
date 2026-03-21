#!/usr/bin/env node
/**
 * 统一配置加载器
 *
 * 用法:
 *   const config = require('./config_loader');
 *   console.log(config.projectRoot);
 *   console.log(config.asr.provider);
 *   console.log(config.getApiKey('asr'));
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

// 自动检测项目根目录（从当前脚本位置向上查找 config.yaml）
function findProjectRoot() {
  let dir = __dirname;
  for (let i = 0; i < 5; i++) {
    if (fs.existsSync(path.join(dir, 'config.yaml'))) {
      return dir;
    }
    dir = path.dirname(dir);
  }
  // fallback: 环境变量
  if (process.env.PODCASTCUT_DIR) {
    return process.env.PODCASTCUT_DIR;
  }
  throw new Error('找不到 config.yaml，请设置环境变量 PODCASTCUT_DIR');
}

const PROJECT_ROOT = findProjectRoot();

// 加载 config.yaml
const configPath = path.join(PROJECT_ROOT, 'config.yaml');
const rawConfig = yaml.load(fs.readFileSync(configPath, 'utf8'));

// 加载 .env（如果存在）
const envPath = path.join(PROJECT_ROOT, '.env');
if (fs.existsSync(envPath)) {
  const envContent = fs.readFileSync(envPath, 'utf8');
  envContent.split('\n').forEach(line => {
    line = line.trim();
    if (line && !line.startsWith('#')) {
      const eqIdx = line.indexOf('=');
      if (eqIdx > 0) {
        const key = line.substring(0, eqIdx).trim();
        const value = line.substring(eqIdx + 1).trim();
        if (!process.env[key]) {
          process.env[key] = value;
        }
      }
    }
  });
}

// 从环境变量名解析实际值
function resolveEnvKey(envVarName) {
  if (!envVarName) return null;
  return process.env[envVarName] || null;
}

// 导出配置对象
const config = {
  projectRoot: rawConfig.paths?.project_root || PROJECT_ROOT,
  outputDir: path.resolve(PROJECT_ROOT, rawConfig.paths?.output_dir || './output'),

  asr: {
    provider: rawConfig.asr?.provider || 'aliyun',
    aliyun: rawConfig.asr?.aliyun || {},
    tencent: rawConfig.asr?.tencent || {},
    local: rawConfig.asr?.local || {},
  },

  upload: {
    strategy: rawConfig.upload?.strategy || 'local_server',
    localServer: rawConfig.upload?.local_server || { port: 8765, use_ngrok: false },
    public: rawConfig.upload?.public || {},
    aliyunOss: rawConfig.upload?.aliyun_oss || {},
    tencentCos: rawConfig.upload?.tencent_cos || {},
  },

  qa: rawConfig.qa || {},

  user: {
    defaultUser: rawConfig.user?.default_user || 'default',
    currentUser: process.env.PODCASTCUT_USER || rawConfig.user?.current_user || rawConfig.user?.default_user || 'default',
  },

  // 获取 API Key 的便捷方法
  getApiKey(service) {
    switch (service) {
      case 'asr':
      case 'aliyun':
        return resolveEnvKey(rawConfig.asr?.aliyun?.api_key_env);
      case 'tencent_secret_id':
        return resolveEnvKey(rawConfig.asr?.tencent?.secret_id_env);
      case 'tencent_secret_key':
        return resolveEnvKey(rawConfig.asr?.tencent?.secret_key_env);
      case 'gemini':
        return resolveEnvKey(rawConfig.qa?.gemini_api_key_env);
      default:
        return null;
    }
  },

  // 获取 skill 目录路径
  skillDir(name) {
    return path.join(this.projectRoot, name);
  },

  // 获取脚本路径
  scriptPath(skill, script) {
    return path.join(this.projectRoot, skill, 'scripts', script);
  },

  // 原始 YAML 配置
  raw: rawConfig,
};

module.exports = config;
