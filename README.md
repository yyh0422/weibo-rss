# 微博用户 RSS（自建）

原来用的自建 RSSHub（38.255.17.24:1200）已失效。微博对无登录抓取直接拦截，
本仓库改用**登录 Cookie** 调用 `m.weibo.cn` 官方 API，每 30 分钟抓取一次，
通过 GitHub Pages 对外提供 RSS。

## 订阅地址

`https://yyh0422.github.io/weibo-rss/<uid>.xml`

| 用户 | 订阅地址 |
|---|---|
| t0mbkeeper的微博 | `https://yyh0422.github.io/weibo-rss/6827625527.xml` |
| tombkeeper | `https://yyh0422.github.io/weibo-rss/1401527553.xml` |
| 开心鸭 | `https://yyh0422.github.io/weibo-rss/7948367302.xml` |

## Cookie 配置（必须）

抓取依赖登录态，Cookie 存放在仓库 Secret `WEIBO_COOKIES` 中：

1. 电脑浏览器登录 `https://weibo.com`（建议用小号）。
2. 按 F12 打开开发者工具 → Network → 刷新页面。
3. 点击任意 `weibo.com` 请求 → Request Headers → 复制 `Cookie` 整串。
4. 仓库 Settings → Secrets and variables → Actions → New repository secret，
   Name 填 `WEIBO_COOKIES`，Value 粘贴 Cookie，保存。
5. Actions → 手动触发一次"更新微博 RSS"验证。

Cookie 会过期（短则几周）：若某天 feed 不再更新，重复以上步骤更新 Secret 即可。
