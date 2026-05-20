# Coze Text Toolbox Plugin

这是一个可部署到 Render 并导入 Coze 的文本工具箱插件。它不依赖 Serper、Tavily 或任何联网搜索 API，所以不需要外部 API Key。

## 功能

- `/health`：健康检查
- `/text_count`：统计字符数、中文字数、英文词数、段落数、句子数
- `/clean_text`：清理多余空格、换行，可选删除 URL 和邮箱
- `/extract_keywords_simple`：按词频粗略提取关键词
- `/academic_check`：检查中文学术文本中的口语化表达、弱化表达、连接词重复、过长句等
- `/formula_template`：根据指标描述生成学术公式说明模板

## Render 部署

1. 把本文件夹里的文件上传到 GitHub 仓库根目录。
2. 在 Render 创建 Web Service。
3. Language 选择 Docker。
4. Root Directory 留空。
5. Environment Variables 可以只填一个：

```env
PLUGIN_API_KEY=你自己设置的一串密钥
```

如果你不填 `PLUGIN_API_KEY`，接口也能运行，但公开部署时不建议裸奔。

6. Advanced 里建议设置：

```text
Health Check Path: /health
Dockerfile Path: ./Dockerfile
Docker Build Context Directory: .
```

7. 部署成功后，Render 会给你一个类似这样的公网地址：

```text
https://websearch-xxxx.onrender.com
```

## Coze 导入

1. 打开 `openapi.yaml`。
2. 把：

```yaml
servers:
  - url: https://YOUR_DEPLOYED_DOMAIN.com
```

改成你的 Render 地址，例如：

```yaml
servers:
  - url: https://websearch-xxxx.onrender.com
```

3. 在 Coze 插件页面通过 OpenAPI YAML 导入。
4. 如果 Coze 要求填写鉴权信息，填写：

```text
Header Name: X-API-Key
Header Value: 你在 Render 设置的 PLUGIN_API_KEY
```

## 本地测试

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 10000
```

测试：

```bash
curl http://localhost:10000/health
```
