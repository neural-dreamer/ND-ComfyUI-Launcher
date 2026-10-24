const token = document.getElementById('token');
const enabled = document.getElementById('enabled');
const status = document.getElementById('status');
const captureState = document.getElementById('capture-state');
const languageToggle = document.getElementById('language-toggle');
const languageMenu = document.getElementById('language-menu');
const languageCurrent = document.getElementById('language-current');
function closeLanguageMenu(returnFocus = false) {
  languageMenu.hidden = true;
  languageToggle.setAttribute('aria-expanded', 'false');
  if (returnFocus) languageToggle.focus();
}
languageToggle.onclick = () => {
  const open = languageMenu.hidden;
  languageMenu.hidden = !open;
  languageToggle.setAttribute('aria-expanded', String(open));
  if (open) languageMenu.querySelector('[aria-pressed="true"]').focus();
};
document.addEventListener('click', event => {
  if (!event.target.closest('.language-picker')) closeLanguageMenu();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && !languageMenu.hidden) {
    closeLanguageMenu(true);
    event.preventDefault();
  }
});
let theme = 'neon';
const themeNames = {ru:['Неон','Туманная ночь','Классик'],en:['Neon','Foggy Night','Classic'],zh:['霓虹','雾夜','经典']};
function renderTheme() {
  document.documentElement.dataset.theme = theme;
  const iconPrefix = theme === 'neon' ? 'icons/nd-' : 'icons/nd-' + theme + '-';
  document.querySelector('header img').src = iconPrefix + '128.png';
  document.querySelector('link[rel="icon"]').href = iconPrefix + '32.png';
  document.querySelector('.theme-picker').setAttribute('aria-label', {ru:'Тема',en:'Theme',zh:'主题'}[language]);
  document.querySelectorAll('button[data-theme]').forEach(button => {
    const name = themeNames[language][['neon','fog','classic'].indexOf(button.dataset.theme)];
    button.title = name;
    button.setAttribute('aria-label', name);
    button.setAttribute('aria-pressed', String(button.dataset.theme === theme));
  });
}
document.querySelectorAll('button[data-theme]').forEach(button => {
  button.onclick = async () => {
    const previous = theme;
    theme = button.dataset.theme;
    renderTheme();
    try { await chrome.storage.local.set({theme}); }
    catch(error) { theme = previous; renderTheme(); setStatus('Не удалось сохранить: ' + error.message); }
  };
});
let language = 'ru';
let statusMessage = '';
let captureError = '';
function translate(message) {
  message = String(message || '');
  if (language === 'ru') return message;
  if (ND_TRANSLATIONS[message]) return ND_TRANSLATIONS[message][language];
  // Background messages retain their original form so they can be retranslated.
  for (const source of Object.keys(ND_TRANSLATIONS)) {
    if (source.endsWith(': ') && message.startsWith(source)) {
      const suffix = message.slice(source.length);
      return ND_TRANSLATIONS[source][language] + (source === 'Передано в лаунчер: ' ? suffix : translate(suffix));
    }
  }
  const connected = 'Связь установлена. ND Launcher ';
  if (message.startsWith(connected)) return ND_TRANSLATIONS[connected][language] + message.slice(connected.length);
  return message;
}
function setStatus(message) {
  statusMessage = message || 'Подключение ещё не проверено.';
  status.textContent = translate(statusMessage);
}
function renderCaptureState() {
  captureState.textContent = translate(captureError || (enabled.checked ? 'Перехват включён' : 'Перехват выключен'));
}
function renderLanguage() {
  renderTheme();
  document.documentElement.lang = language === 'zh' ? 'zh-CN' : language;
  languageCurrent.textContent = {ru:'РУ', en:'EN', zh:'中文'}[language];
  document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = translate(el.dataset.i18n); });
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => { el.placeholder = translate(el.dataset.i18nPlaceholder); });
  document.querySelectorAll('[data-lang]').forEach(el => { el.setAttribute('aria-pressed', String(el.dataset.lang === language)); });
  renderCaptureState();
  setStatus(statusMessage);
}
document.querySelectorAll('[data-lang]').forEach(button => {
  button.onclick = async () => {
    const previous = language;
    language = button.dataset.lang;
    closeLanguageMenu(true);
    renderLanguage();
    try { await chrome.storage.local.set({language}); }
    catch (error) { language = previous; renderLanguage(); setStatus('Не удалось сохранить: ' + error.message); }
  };
});
enabled.onchange = async () => {
  enabled.disabled = true;
  captureError = '';
  try {
    await chrome.storage.local.set({enabled: enabled.checked});
  } catch (error) {
    enabled.checked = !enabled.checked;
    captureError = 'Не удалось сохранить: ' + error.message;
  } finally {
    renderCaptureState();
    enabled.disabled = false;
  }
};
async function refresh() {
  const data = await chrome.storage.local.get(['token','enabled','lastStatus','language','theme']);
  theme = ['neon','fog','classic'].includes(data.theme) ? data.theme : 'neon';
  language = ['ru','en','zh'].includes(data.language) ? data.language : 'ru';
  token.value = data.token || ''; enabled.checked = data.enabled !== false;
  enabled.disabled = false;
  statusMessage = data.lastStatus || 'Подключение ещё не проверено.';
  renderLanguage();
}
document.getElementById('save').onclick = async () => {
  try {
    await chrome.storage.local.set({token:token.value.trim(),enabled:enabled.checked});
    setStatus('Настройки сохранены.');
  } catch (error) { setStatus('Не удалось сохранить: ' + error.message); }
};
document.getElementById('ping').onclick = async () => {
  try {
    await chrome.storage.local.set({token:token.value.trim(),enabled:enabled.checked});
    const r = await chrome.runtime.sendMessage({action:'ping'});
    setStatus(r.ok ? 'Связь установлена. ND Launcher ' + r.version : r.error);
  } catch(error) { setStatus(error.message); }
};
document.getElementById('retry').onclick = async () => {
  setStatus('Проверяю ожидающие передачи…');
  try { await chrome.runtime.sendMessage({action:'retry'}); await refresh(); }
  catch(error) { setStatus(error.message); }
};
refresh().catch(error => setStatus(error.message));
