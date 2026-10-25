/* Loopback request to ND Launcher; used by the service worker and the settings page. */
const BASE = 'http://127.0.0.1:17863';
// targetAddressSpace tells Chrome's Local Network Access
// check that the loopback request is intended; older Chrome ignores the option.
const NO_LAUNCHER = 'Лаунчер не отвечает. Проверьте, что он запущен и в его настройках включён приём загрузок из браузера. Если всё включено, разрешите расширению доступ к локальной сети: chrome://extensions → ND Launcher → Сведения → Настройки сайтов.';
async function bridgeFetch(action, data, token) {
  let response, result;
  try {
    response = await fetch(BASE + '/' + action, {
      method: 'POST', headers: {'Content-Type': 'application/json', 'X-ND-Token': token},
      body: JSON.stringify(data), signal: AbortSignal.timeout(12000), targetAddressSpace: 'loopback'
    });
  } catch (error) {
    throw new Error(error?.name === 'TimeoutError' ? 'Лаунчер не ответил вовремя.' : NO_LAUNCHER);
  }
  try { result = await response.json(); }
  catch { throw new Error('На порту 17863 отвечает другая программа, а не ND Launcher.'); }
  if (!response.ok || !result.ok) throw new Error(result.error || 'Лаунчер не принял задание.');
  return result;
}
