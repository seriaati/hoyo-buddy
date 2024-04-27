from typing import Final

PAGE: Final[str] = """
    <!DOCTYPE html>
    <html>

      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Hoyo Buddy | Login web server</title>
      </head>

      <style>
        body {
          background-color: #36393f;
        }
      </style>

      <body></body>
      <script src="./gt/v{gt_version}.js"></script>
      <script>
        const geetestVersion = {gt_version};
        const initGeetest = geetestVersion === 3 ? window.initGeetest : window.initGeetest4;
        fetch("/mmt")
          .then((response) => response.json())
          .then((mmt) => {
            const initParams = geetestVersion === 3 ? {
              gt: mmt.gt,
              challenge: mmt.challenge,
              new_captcha: mmt.new_captcha,
              api_server: '{api_server}',
              https: /^https/i.test(window.location.protocol),
              product: "bind",
              lang: 'en',
            } : {
              captchaId: mmt.gt,
              riskType: mmt.risk_type,
              userInfo: mmt.session_id ? JSON.stringify({
                mmt_key: mmt.session_id
              }) : undefined,
              api_server: '{api_server}',
              product: "bind",
              language: 'en',
            };
            initGeetest(
              initParams,
              (captcha) => {
                captcha.onReady(() => {
                  captcha.verify();
                });
                captcha.onSuccess(() => {
                  fetch("/send-data", {
                    method: "POST",
                    body: JSON.stringify({
                      ...(mmt.session_id && {session_id: mmt.session_id}),
                      ...(mmt.check_id && {check_id: mmt.check_id}),
                      ...captcha.getValidate(),
                      user_id: {user_id},
                    }),
                  }).then(() => {
                      window.location.href = "/redirect?channel_id={channel_id}&guild_id={guild_id}&message_id={message_id}";
                    });
                });
              }
            )
          });
        if ({proxy_geetest}) {
          Object.defineProperty(HTMLScriptElement.prototype, 'src', {
            get: function() {
              return this.getAttribute('src')
            },
            set: function(url) {
              const proxyPrefixes = [
                /^http:\\/\\/.*\\.geevisit\\.com/,
                /^{api_server}/
              ];
              const prefix = proxyPrefixes.find((prefix) => url.match(prefix));
              if (prefix) {
                console.debug('[Proxy] Request URL override:');
                console.debug('From: ' + url);
                newUrl = new URL(url);
                newUrl.searchParams.set('url', newUrl.origin + newUrl.pathname);
                url = window.location.origin + '/proxy' + newUrl.search;
                console.debug('To: ' + url);
              }
              this.setAttribute('src', url);
            }
          });
        }
      </script>
    </html>
"""
