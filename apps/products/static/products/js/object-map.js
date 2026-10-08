/* Яндекс Карты только для публичной карточки. */
(() => {
    "use strict";
    let apiPromise;
    const escapeText = text => {
        const div = document.createElement("div");
        div.textContent = text;
        return div.innerHTML;
    };
    const loadApi = key => {
        if (!apiPromise) {
            apiPromise = new Promise((resolve, reject) => {
                const script = document.createElement("script");
                const url = new URL("https://api-maps.yandex.ru/2.1/");
                url.search = new URLSearchParams({apikey:key, lang:"ru_RU", coordorder:"longlat", ns:"dikarYmaps"});
                script.src = url.href;
                script.async = true;
                const timer = setTimeout(() => fail(), 20000);
                const fail = () => { clearTimeout(timer); script.remove(); reject(new Error("Не удалось загрузить Яндекс Карты. Проверьте подключение и ключ API.")); };
                script.onerror = fail;
                script.onload = () => {
                    const api = window.dikarYmaps;
                    if (!api) return fail();
                    api.ready(() => { clearTimeout(timer); resolve(api); }, fail);
                };
                document.head.append(script);
            }).catch(error => { apiPromise = null; throw error; });
        }
        return apiPromise;
    };
    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("[data-object-map-public]").forEach(root => {
            const button = root.querySelector(".object-map__load");
            if (!button) return;
            const canvas = root.querySelector(".object-map__canvas");
            const status = root.querySelector(".object-map__status");
            let data;
            try { data = JSON.parse(document.getElementById(root.dataset.config).textContent); }
            catch { status.textContent = "Не удалось прочитать данные карты."; return; }
            button.addEventListener("click", async () => {
                button.disabled = true;
                status.textContent = "Загрузка карты…";
                let map;
                try {
                    const api = await loadApi(data.api_key);
                    canvas.hidden = false;
                    map = new api.Map(canvas, {
                        center:data.center.map(Number), zoom:data.zoom,
                        controls:["zoomControl", "fullscreenControl"],
                    }, {minZoom:0, maxZoom:19});
                    map.behaviors.disable("scrollZoom");
                    map.geoObjects.add(new api.Placemark(data.marker.map(Number), {
                        balloonContentHeader:escapeText(data.title),
                        balloonContentBody:escapeText(data.address),
                        hintContent:escapeText(data.title),
                    }, {preset:"islands#redDotIcon", draggable:false}));
                    button.hidden = true;
                    status.textContent = "";
                } catch (error) {
                    if (map) map.destroy();
                    canvas.hidden = true;
                    button.disabled = false;
                    status.textContent = error.message;
                }
            });
        });
    });
})();
