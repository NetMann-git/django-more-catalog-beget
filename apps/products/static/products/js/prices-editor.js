/* TinyMCE для поля «Цены»: локальные файлы и сохранение исходника без правок. */
(() => {
  'use strict';
  function start() {
    if (!window.tinymce) return; // Без JS остаётся исходный HTML в textarea.
    document.querySelectorAll('textarea[data-prices-editor]').forEach(raw => {
      if (raw.dataset.initialized) return;
      raw.dataset.initialized = '1';
      const original = raw.value;
      const preview = raw.nextElementSibling;
      const initial = preview?.classList.contains('prices-editor__initial') ? preview.value : original;
      const visual = document.createElement('textarea');
      visual.id = raw.id + '_visual'; visual.setAttribute('aria-label', 'Цены');
      visual.value = initial; raw.after(visual);
      preview?.classList.contains('prices-editor__initial') && preview.remove();
      let initialized = false, baseline = null;
      const script = document.querySelector('script[src*="vendor/tinymce/tinymce.min.js"]');
      const base = script.src.slice(0, script.src.lastIndexOf('/'));
      // Only the original textarea has a name and is submitted. TinyMCE edits a
      // separate unnamed textarea, so its automatic save cannot rewrite original HTML.
      window.tinymce.init({
        target: visual,
        base_url: base,
        suffix: '.min',
        license_key: 'gpl',
        language: 'ru',
        language_url: base + '/langs/ru.js',
        height: 560,
        min_height: 350,
        resize: true,
        promotion: false,
        branding: true,
        menubar: 'edit view insert format table tools',
        plugins: 'advlist autolink lists link image charmap preview anchor searchreplace visualblocks code fullscreen insertdatetime media table wordcount directionality',
        toolbar: 'undo redo | blocks fontfamily fontsize | bold italic underline forecolor backcolor | alignleft aligncenter alignright | bullist numlist | table link image media | code fullscreen',
        toolbar_mode: 'wrap',
        contextmenu: 'link image table',
        table_toolbar: 'tableprops tabledelete | tableinsertrowbefore tableinsertrowafter tabledeleterow | tableinsertcolbefore tableinsertcolafter tabledeletecol | tablemergecells tablesplitcells',
        table_default_attributes: {class: 'table table-bordered'},
        table_default_styles: {'border-collapse': 'collapse', width: '100%'},
        table_resize_bars: true,
        table_advtab: true,
        table_cell_advtab: true,
        table_row_advtab: true,
        media_live_embeds: false,
        media_filter_html: true,
        sandbox_iframes: true,
        sandbox_iframes_exclusions: [],
        convert_unsafe_embeds: true,
        xss_sanitization: true,
        convert_urls: false,
        relative_urls: false,
        remove_script_host: false,
        entity_encoding: 'raw',
        invalid_elements: 'script,style,svg,math,object,embed,form,input,button,textarea,select,template,base,link,meta',
        extended_valid_elements: 'iframe[src|width|height|title|class|style|sandbox|allowfullscreen|loading|referrerpolicy],video[src|controls|width|height|poster|preload|class|style],source[src|type],col[span|width|style|class]',
        content_security_policy: "default-src 'none'; img-src https: 'self' data: blob:; media-src https: 'self' blob:; style-src 'self' 'unsafe-inline'; font-src 'self'; frame-src 'none';",
        content_style: 'body{font:16px Arial,sans-serif;line-height:1.5;color:#172536}table{border-collapse:collapse}td,th{border:1px solid #94a3b8;padding:8px}img,video{max-width:100%;height:auto}.table-responsive{overflow-x:auto}.table-striped tr:nth-child(even){background:#f1f5f9}',
        setup(editor) {
          editor.on('BeforeSetContent', event => {
            if (!initialized && !event.selection && !event.paste) event.content = initial;
          });
          function sync() {
            if (!initialized) return;
            const html = editor.getContent();
            raw.value = html === baseline ? original : html;
          }
          editor.on('init', () => {
            baseline = editor.getContent(); initialized = true;
            raw.hidden = true; editor.setDirty(false);
            raw.form?.addEventListener('submit', sync);
          });
          editor.on('input change undo redo', sync);
          editor.ui.registry.addMenuItem('panorama', {
            text: 'Панорама Яндекс Карт',
            onAction() {
              editor.windowManager.open({
                title: 'Добавить панораму Яндекс Карт',
                body: {type:'panel', items:[{type:'input',name:'url',label:'Адрес iframe: https://yandex.ru/map-widget/…'}]},
                buttons: [{type:'cancel',text:'Отмена'},{type:'submit',text:'Добавить',primary:true}],
                onSubmit(api) {
                  const value = api.getData().url.trim();
                  let url;
                  try { url = new URL(value); } catch { return editor.windowManager.alert('Укажите HTTPS-адрес виджета Яндекс Карт.'); }
                  if (url.protocol !== 'https:' || url.hostname !== 'yandex.ru' || !url.pathname.startsWith('/map-widget/') || url.username || url.password || (url.port && url.port !== '443')) return editor.windowManager.alert('Разрешён адрес https://yandex.ru/map-widget/…');
                  const encoded = editor.dom.encode(value);
                  editor.insertContent('<iframe src="'+encoded+'" width="560" height="400" title="Панорама Яндекс Карт" sandbox="" allowfullscreen=""></iframe><p></p>');
                  sync(); api.close();
                }
              });
            }
          });
        },
        menu: {
          insert: {title:'Insert',items:'image link media panorama inserttable | charmap anchor insertdatetime'},
          tools: {title:'Tools',items:'code wordcount'}
        }
      }).catch(() => {
        visual.remove(); raw.value = original; raw.hidden = false; delete raw.dataset.initialized;
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded',start); else start();
})();
