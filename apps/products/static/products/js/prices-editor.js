/* Локальный HTML-редактор. В iframe нет разрешения на исполнение скриптов. */
(() => {
  'use strict';
  function init(raw) {
    if (raw.dataset.initialized) return;
    raw.dataset.initialized = '1';
    const initial = raw.nextElementSibling;
    const box = document.createElement('div'); box.className = 'prices-editor';
    raw.before(box);
    const bar = document.createElement('div'); bar.className = 'prices-editor__toolbar';
    box.append(bar); box.append(raw); raw.hidden = true;
    const frame = document.createElement('iframe'); frame.className = 'prices-editor__frame';
    frame.title = 'Визуальный редактор цен'; frame.setAttribute('sandbox', 'allow-same-origin');
    box.append(frame);
    const note = document.createElement('div'); note.className = 'prices-editor__notice';
    note.textContent = 'Таблицы: Ctrl + щелчок выбирает ячейки для объединения. HTML сохраняется без изменения до первой правки. Панорамы проверяйте в карточке объекта после сохранения.';
    box.append(note);
    let doc, visual = true, ready = false;
    const selected = new Set();
    const style = 'body{font:16px Arial;padding:16px;color:#172536;overflow-wrap:anywhere}table{border-collapse:collapse;width:100%}td,th{border:1px solid #94a3b8;padding:8px;min-width:45px}img,video,iframe{max-width:100%}td[data-selected],th[data-selected]{outline:3px solid #3b82f6}';
    // CSP is additional defence for raw HTML preview, including pasted markup.
    const prefix = '<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; img-src https: &#39;self&#39;; media-src https: &#39;self&#39;; style-src &#39;unsafe-inline&#39;; frame-src &#39;none&#39;; form-action &#39;none&#39;;"><style>' + style + '</style></head><body contenteditable="true">';
    function clearSelection() { selected.forEach(c => c.removeAttribute('data-selected')); selected.clear(); }
    function sync() {
      if (!ready || !visual) return;
      const clone = doc.body.cloneNode(true);
      clone.querySelectorAll('[data-selected]').forEach(c => c.removeAttribute('data-selected'));
      raw.value = clone.innerHTML;
    }
    function cleanPreview(html) {
      html = html.replace(/\{source(?:\s+[^}]*)?\}([\s\S]*?)\{\/source\}/gi, (_, text) => {
        if (!text.includes('&lt;')) return text;
        return new DOMParser().parseFromString(text, 'text/html').body.textContent;
      });
      const parsed = new DOMParser().parseFromString(html, 'text/html');
      parsed.querySelectorAll('script,style,meta,base,link,svg,math,object,embed,form,input,button,textarea,select,template').forEach(el => el.remove());
      parsed.querySelectorAll('*').forEach(el => Array.from(el.attributes).forEach(attr => {
        if (/^on/i.test(attr.name) || ['srcdoc', 'contenteditable', 'autofocus'].includes(attr.name)) el.removeAttribute(attr.name);
      }));
      return parsed.body.innerHTML;
    }
    function load(html) {
      ready = false;
      frame.onload = () => {
        doc = frame.contentDocument; ready = true;
        doc.body.addEventListener('input', sync);
        doc.body.addEventListener('click', e => {
          if (e.target.closest('a')) e.preventDefault();
          const cell = e.target.closest('td,th');
          if (cell && (e.ctrlKey || e.metaKey)) {
            e.preventDefault();
            if (selected.has(cell)) { selected.delete(cell); cell.removeAttribute('data-selected'); }
            else { selected.add(cell); cell.setAttribute('data-selected', 'true'); }
          }
        });
        doc.body.addEventListener('paste', e => {
          e.preventDefault();
          const rich = e.clipboardData.getData('text/html');
          if (rich) doc.execCommand('insertHTML', false, cleanPreview(rich));
          else doc.execCommand('insertText', false, e.clipboardData.getData('text/plain'));
          sync();
        });
        doc.body.addEventListener('drop', e => e.preventDefault());
      };
      // Scripts, event attributes, forms, external styles and nested frames cannot run under this sandbox/CSP.
      frame.srcdoc = prefix + cleanPreview(html) + '</body></html>';
    }
    function button(label, action) {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = label;
      b.addEventListener('mousedown', e => e.preventDefault());
      b.addEventListener('click', () => {
        if (!visual || !ready) { if (label !== 'HTML / Визуально') alert('Сначала откройте визуальный режим.'); }
        else frame.contentWindow.focus();
        action();
      }); bar.append(b); return b;
    }
    function command(name, value) { if (visual && ready) { doc.execCommand(name, false, value); sync(); } }
    function insert(html) { command('insertHTML', html); }
    function esc(s) { const el = document.createElement('span'); el.textContent = s; return el.innerHTML.replace(/"/g, '&quot;'); }
    function askUrl(label, frameUrl = false) {
      const url = prompt(label); if (!url) return null;
      if (frameUrl ? !/^https:\/\/(yandex\.ru\/map-widget\/|www\.youtube(?:-nocookie)?\.com\/embed\/|player\.vimeo\.com\/video\/|rutube\.ru\/play\/embed\/)/.test(url) : !/^(https:\/\/|\/(?!\/)|images\/|media\/|mailto:|tel:)/.test(url)) {
        alert('Нужен HTTPS-адрес разрешённого сервиса или локальный путь /media/…'); return null;
      }
      return esc(url);
    }
    function currentCell() {
      const node = doc.getSelection()?.anchorNode;
      return (node?.nodeType === 1 ? node : node?.parentElement)?.closest('td,th');
    }
    function grid(table) {
      const cells = [], positions = new Map();
      Array.from(table.rows).forEach((row, r) => {
        cells[r] ||= []; let col = 0;
        Array.from(row.cells).forEach(cell => {
          while (cells[r][col]) col++;
          positions.set(cell, [r, col]);
          for (let y = r; y < r + cell.rowSpan; y++) {
            cells[y] ||= [];
            for (let x = col; x < col + cell.colSpan; x++) cells[y][x] = cell;
          }
          col += cell.colSpan;
        });
      }); return {cells, positions};
    }
    [['Жирный','bold'],['Курсив','italic'],['Подчеркнуть','underline'],['Список','insertUnorderedList'],['Нумерация','insertOrderedList'],['Слева','justifyLeft'],['По центру','justifyCenter'],['Справа','justifyRight'],['Отменить','undo'],['Повторить','redo']].forEach(([label,cmd]) => button(label, () => command(cmd)));
    button('Заголовок', () => { const n = prompt('Уровень заголовка: 2, 3 или 4', '3'); if (/^[234]$/.test(n)) command('formatBlock', 'h' + n); });
    button('Абзац', () => command('formatBlock','p'));
    button('Цвет', () => { const color = prompt('Цвет, например #ff0000', '#ff0000'); if (/^#[\da-f]{6}$/i.test(color)) command('foreColor', color); });
    button('Размер', () => { const n = prompt('Размер от 1 до 7', '3'); if (/^[1-7]$/.test(n)) command('fontSize', n); });
    button('Ссылка', () => { const url = askUrl('Адрес ссылки'); if (url) command('createLink', url.replace(/&quot;/g,'"').replace(/&amp;/g,'&')); });
    button('Изображение', () => { const url = askUrl('Адрес изображения'); if (url) insert('<img src="' + url + '" alt="">'); });
    button('Видео', () => { const url = askUrl('Адрес файла видео (HTTPS или /media/…)'); if (url) insert('<video src="' + url + '" controls preload="metadata" width="560"></video><p><br></p>'); });
    button('Панорама / видеовставка', () => { const url = askUrl('Адрес iframe: Яндекс map-widget, YouTube embed, Vimeo video, RuTube play/embed',true); if (url) insert('<iframe src="' + url + '" width="560" height="400" title="Карта или видео"></iframe><p><br></p>'); });
    button('Таблица', () => {
      if (!visual || !ready) return;
      const rows = Number(prompt('Количество строк', '3')), cols = Number(prompt('Количество столбцов', '4'));
      if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows < 1 || cols < 1 || rows > 40 || cols > 24) return;
      insert('<table class="table table-striped table-bordered"><tbody>' + Array.from({length:rows}, () => '<tr>' + '<td><br></td>'.repeat(cols) + '</tr>').join('') + '</tbody></table><p><br></p>');
    });
    function simpleTable(action) {
      if (!visual || !ready) return;
      const cell = currentCell(); if (!cell) return alert('Поставьте курсор в ячейку.');
      const table = cell.closest('table');
      if (Array.from(table.querySelectorAll('td,th')).some(c => c.colSpan > 1 || c.rowSpan > 1)) return alert('Для изменения строк и столбцов сначала разделите объединённые ячейки либо используйте HTML.');
      clearSelection(); action(cell,table); sync();
    }
    button('+ строка', () => simpleTable((cell, table) => {
      const row = table.insertRow(cell.parentElement.rowIndex + 1);
      for (let i=0; i<cell.parentElement.cells.length; i++) row.insertCell().innerHTML = '<br>';
    }));
    button('− строка', () => simpleTable((cell,table) => table.deleteRow(cell.parentElement.rowIndex)));
    button('+ столбец', () => simpleTable((cell,table) => Array.from(table.rows).forEach(row => { row.insertCell(cell.cellIndex + 1).innerHTML = '<br>'; })));
    button('− столбец', () => simpleTable((cell,table) => { const n = cell.cellIndex; Array.from(table.rows).forEach(row => row.deleteCell(n)); }));
    button('Объединить', () => {
      if (!visual || !ready || selected.size < 2) return;
      const list = [...selected], table = list[0].closest('table');
      if (list.some(c => c.closest('table') !== table)) return alert('Выберите ячейки одной таблицы.');
      const {cells,positions} = grid(table);
      const minR = Math.min(...list.map(c=>positions.get(c)[0])), minC = Math.min(...list.map(c=>positions.get(c)[1]));
      const maxR = Math.max(...list.map(c=>positions.get(c)[0]+c.rowSpan-1)), maxC = Math.max(...list.map(c=>positions.get(c)[1]+c.colSpan-1));
      for (let r=minR;r<=maxR;r++) for (let c=minC;c<=maxC;c++) if (!selected.has(cells[r]?.[c])) return alert('Выберите прямоугольник ячеек целиком.');
      const anchor = cells[minR][minC], content = list.sort((a,b)=>positions.get(a)[0]-positions.get(b)[0] || positions.get(a)[1]-positions.get(b)[1]).map(c=>c.innerHTML).join('<br>');
      clearSelection(); list.filter(c=>c!==anchor).forEach(c=>c.remove()); anchor.colSpan=maxC-minC+1; anchor.rowSpan=maxR-minR+1; anchor.innerHTML=content; sync();
    });
    button('Разделить', () => {
      if (!visual || !ready) return;
      const cell=currentCell(); if (!cell || (cell.colSpan===1 && cell.rowSpan===1)) return;
      const table=cell.closest('table'), {cells,positions}=grid(table), [r,c]=positions.get(cell), rs=cell.rowSpan, cs=cell.colSpan;
      clearSelection(); cell.removeAttribute('colspan');cell.removeAttribute('rowspan');
      for (let y=r;y<r+rs;y++) {
        const row=table.rows[y]; if (!row) continue;
        const reference=Array.from(row.cells).find(item=>item!==cell && positions.get(item)[1]>=c+cs);
        for(let x=c;x<c+cs;x++) if(y!==r || x!==c) { const item=doc.createElement(cell.tagName); item.innerHTML='<br>'; row.insertBefore(item,reference || null); }
      } sync();
    });
    button('Удалить таблицу', () => { if (visual && ready) { const cell=currentCell();if(cell && confirm('Удалить таблицу целиком?')) { clearSelection();cell.closest('table').remove();sync(); } } });
    button('HTML / Визуально', () => {
      if (visual) { clearSelection(); visual=false; frame.hidden=true; raw.hidden=false; raw.focus(); }
      else { visual=true; raw.hidden=true; frame.hidden=false; selected.clear();load(raw.value); }
    });
    load(initial?.value || ''); initial?.remove();
  }
  function start() { document.querySelectorAll('textarea[data-prices-editor]').forEach(init); }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
