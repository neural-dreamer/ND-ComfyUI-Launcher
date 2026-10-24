/* Two-phase handoff. Never cancel Chrome before the launcher reserves the target. */
const BASE = 'http://127.0.0.1:17863';
const active = new Set();
function redUrl(value) {
  try { const u = new URL(value); return u.protocol === 'https:' && ['civitai.red','www.civitai.red','civitai.com','www.civitai.com','huggingface.co','www.huggingface.co','modelscope.cn','www.modelscope.cn'].includes(u.hostname) && !u.username && !u.password && (!u.port || u.port === "443"); }
  catch { return false; }
}
function candidate(item) {
  return !item.incognito && (redUrl(item.url) || redUrl(item.referrer)) &&
    /\.(safetensors|ckpt|pt|pth|bin|gguf|zip)$/i.test(item.filename || '') &&
    /^[a-z]:[\\/]/i.test(item.filename || '');
}
async function api(action, data) {
  const {token = ''} = await chrome.storage.local.get('token');
  if (!token) throw new Error('Сначала укажите ключ подключения.');
  const response = await fetch(BASE + '/' + action, {
    method: 'POST', headers: {'Content-Type': 'application/json', 'X-ND-Token': token},
    body: JSON.stringify(data), signal: AbortSignal.timeout(12000)
  });
  const result = await response.json();
  if (!response.ok || !result.ok) throw new Error(result.error || 'Лаунчер не принял задание.');
  return result;
}
async function status(message, failed = false) {
  await chrome.storage.local.set({lastStatus: message});
  await chrome.action.setBadgeText({text: failed ? '!' : ''});
  await chrome.action.setBadgeBackgroundColor({color: failed ? '#a84343' : '#24775d'});
}
const keyFor = id => 'pending_' + id;
async function savePending(id, record) { await chrome.storage.local.set({[keyFor(id)]: record}); }
async function commit(id, record) {
  // Re-prepare is idempotent, and restores a reservation after a launcher restart.
  await api('prepare', record.payload);
  await api('commit', {request_id: record.payload.request_id});
  await chrome.storage.local.remove(keyFor(id));
  await status('Передано в лаунчер: ' + record.payload.filename.split(/[\\/]/).pop());
}
async function handoff(id) {
  if (active.has(id)) return;
  active.add(id);
  let pausedByUs = false, cancelled = false, record = null;
  try {
    const settings = await chrome.storage.local.get(['enabled', 'token', keyFor(id)]);
    if (!settings.enabled || !settings.token || settings[keyFor(id)]) return;
    let [item] = await chrome.downloads.search({id});
    if (!item || !candidate(item) || item.state !== 'in_progress' || item.paused ||
        !['safe','accepted','allowlistedByPolicy'].includes(item.danger)) return;
    // Stop browser I/O before waiting for any launcher network round-trip.
    await chrome.downloads.pause(id);
    pausedByUs = true;
    await api('ping', {});
    [item] = await chrome.downloads.search({id});
    if (!item || item.state !== 'in_progress' || !item.paused) throw new Error('Загрузка уже завершена или остановлена.');
    record = {phase: 'prepared', payload: {
      request_id: crypto.randomUUID(), url: item.url, final_url: item.finalUrl || item.url,
      referrer: item.referrer || '', filename: item.filename, total_bytes: Math.max(0,item.totalBytes || 0)
    }};
    await api('prepare', record.payload);
    // Write recovery data BEFORE cancelling: a suspended service worker can retry safely.
    await savePending(id, record);
    await chrome.downloads.cancel(id);
    cancelled = true;
    [item] = await chrome.downloads.search({id});
    if (!item || item.state !== 'interrupted') {
      cancelled = false;
      await chrome.storage.local.remove(keyFor(id));
      throw new Error('Браузер уже завершил загрузку; повторное скачивание не начато.');
    }
    record.phase = 'cancelled';
    await savePending(id, record);
    await commit(id, record);
  } catch (error) {
    if (!cancelled) {
      if (pausedByUs) await chrome.downloads.resume(id).catch(() => {});
      await chrome.storage.local.remove(keyFor(id));
      await status('Загрузка оставлена в браузере: ' + error.message, true);
    } else {
      await status('Ожидает передачи в лаунчер. Нажмите «Повторить передачу»: ' + error.message, true);
    }
  } finally { active.delete(id); }
}
async function retryPending() {
  const data = await chrome.storage.local.get(null);
  if (!data.enabled) return;
  for (const [key, record] of Object.entries(data)) {
    if (!key.startsWith('pending_') || !record?.payload) continue;
    const id = Number(key.slice(8));
    if (active.has(id)) continue;
    active.add(id);
    try {
      const [item] = await chrome.downloads.search({id});
      if (item?.state === 'complete') { await chrome.storage.local.remove(key); continue; }
      if (item?.state === 'in_progress') {
        // A worker died before cancellation. Let Chrome keep the file instead.
        if (item.paused) await chrome.downloads.resume(id);
        await chrome.storage.local.remove(key);
        continue;
      }
      if (record.phase === 'prepared' && !item) {
        await status('Неизвестно состояние загрузки. Проверьте историю Chrome перед повтором.', true);
        continue;
      }
      await commit(id, record);
    } catch (error) { await status('Передача ожидает лаунчер: ' + error.message, true); }
    finally { active.delete(id); }
  }
}
// filename is assigned after Chrome resolves the target (including Save As).
// Do not use onDeterminingFilename's tentative name or guess a destination.
chrome.downloads.onChanged.addListener(delta => {
  if (delta.filename?.current) handoff(delta.id).catch(() => {});
});
chrome.runtime.onInstalled.addListener(async details => {
  const {enabled} = await chrome.storage.local.get('enabled');
  if (enabled === undefined) await chrome.storage.local.set({enabled: true});
  await chrome.alarms.create('retry-handoff', {periodInMinutes: 1});
  if (details.reason === 'install') await chrome.runtime.openOptionsPage();
});
chrome.runtime.onStartup.addListener(async () => {
  await chrome.alarms.create('retry-handoff', {periodInMinutes: 1});
  await retryPending();
});
chrome.alarms.onAlarm.addListener(alarm => { if (alarm.name === 'retry-handoff') retryPending().catch(() => {}); });
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (sender.id !== chrome.runtime.id) return;
  if (message.action === 'ping') {
    api('ping', {}).then(result => sendResponse(result)).catch(error => sendResponse({ok:false,error:error.message}));
    return true;
  }
  if (message.action === 'retry') {
    retryPending().then(() => sendResponse({ok:true})).catch(error => sendResponse({ok:false,error:error.message}));
    return true;
  }
});

// Reapply the saved palette whenever the worker starts or the theme changes.
let iconUpdate = Promise.resolve();
function refreshThemeIcon() {
  iconUpdate = iconUpdate.catch(() => {}).then(async () => {
    const {theme} = await chrome.storage.local.get('theme');
    const prefix = ['fog', 'classic'].includes(theme) ? 'icons/nd-' + theme + '-' : 'icons/nd-';
    const path = Object.fromEntries([16, 32, 48, 128].map(size => [size, prefix + size + '.png']));
    await chrome.action.setIcon({path});
  });
  return iconUpdate;
}
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.theme) refreshThemeIcon().catch(() => {});
});
refreshThemeIcon().catch(() => {});
