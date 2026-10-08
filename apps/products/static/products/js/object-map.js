/* Одно подключение API, координаты longlat; исходные поля не переписываются при загрузке. */
(() => {
    "use strict";
    let apiPromise;
    const pair = value => {
        if (!String(value || "").trim()) return null;
        const parts = String(value).split(",");
        if (parts.length !== 2 || parts.some(part => !part.trim())) throw new Error("Введите долготу и широту через запятую.");
        const result = parts.map(Number);
        if (!result.every(Number.isFinite) || Math.abs(result[0]) > 180 || Math.abs(result[1]) > 90) throw new Error("Проверьте диапазон координат.");
        return result;
    };
    const zoomValue = value => {
        const result = String(value ?? "").trim() === "" ? 12 : Number(value);
        if (!Number.isInteger(result) || result < 0 || result > 19) throw new Error("Масштаб должен быть целым числом от 0 до 19.");
        return result;
    };
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
        document.querySelectorAll("[data-object-map-editor], [data-object-map-public]").forEach(root => {
            const button = root.querySelector(".object-map__load");
            if (!button) return;
            const editor = root.hasAttribute("data-object-map-editor");
            const canvas = root.querySelector(".object-map__canvas");
            const status = root.querySelector(".object-map__status");
            let data;
            if (!editor) {
                try { data = JSON.parse(document.getElementById(root.dataset.config).textContent); }
                catch { status.textContent = "Не удалось прочитать данные карты."; return; }
            }
            const markerInput = editor && document.getElementById(root.dataset.markerInput);
            const centerInput = editor && document.getElementById(root.dataset.centerInput);
            const zoomInput = editor && document.getElementById(root.dataset.zoomInput);
            if (editor && (!markerInput || !centerInput || !zoomInput)) return;
            button.addEventListener("click", async () => {
                button.disabled = true;
                status.textContent = "Загрузка карты…";
                let map;
                try {
                    const markerCoords = editor ? pair(markerInput.value) : data.marker.map(Number);
                    const center = editor ? (pair(centerInput.value) || markerCoords || [39.920664, 43.428032]) : data.center.map(Number);
                    const zoom = zoomValue(editor ? zoomInput.value : data.zoom);
                    const api = await loadApi(editor ? root.dataset.apiKey : data.api_key);
                    canvas.hidden = false;
                    map = new api.Map(canvas, {center, zoom, controls:["zoomControl", "fullscreenControl"]}, {minZoom:0, maxZoom:19});
                    map.behaviors.disable("scrollZoom");
                    let marker;
                    const setMarker = coords => {
                        if (!coords) { if (marker) map.geoObjects.remove(marker); marker = null; return; }
                        if (marker) { marker.geometry.setCoordinates(coords); return; }
                        marker = new api.Placemark(coords, editor ? {} : {
                            balloonContentHeader:escapeText(data.title), balloonContentBody:escapeText(data.address), hintContent:escapeText(data.title),
                        }, {preset:"islands#redDotIcon", draggable:editor});
                        map.geoObjects.add(marker);
                        if (editor) marker.events.add("dragend", () => { markerInput.value = marker.geometry.getCoordinates().join(", "); });
                    };
                    setMarker(markerCoords);
                    if (editor) {
                        let lastCenter = [...map.getCenter()], lastZoom = map.getZoom();
                        map.events.add("click", event => {
                            const coords = event.get("coords");
                            markerInput.value = coords.join(", ");
                            setMarker(coords);
                        });
                        map.events.add("boundschange", () => {
                            const current = map.getCenter(), currentZoom = map.getZoom();
                            if (current.some((number, i) => number !== lastCenter[i])) centerInput.value = current.join(", ");
                            if (currentZoom !== lastZoom) zoomInput.value = String(currentZoom);
                            lastCenter = [...current]; lastZoom = currentZoom;
                        });
                        const updateInputs = () => {
                            try {
                                const coords = pair(markerInput.value);
                                const nextCenter = pair(centerInput.value) || coords || [39.920664, 43.428032];
                                const nextZoom = zoomValue(zoomInput.value);
                                setMarker(coords);
                                lastCenter = [...nextCenter]; lastZoom = nextZoom;
                                map.setCenter(nextCenter, nextZoom);
                                status.textContent = "";
                            } catch (error) { status.textContent = error.message; }
                        };
                        [markerInput, centerInput, zoomInput].forEach(input => input.addEventListener("change", updateInputs));
                        const centerButton = root.querySelector(".object-map__center");
                        centerButton.hidden = false;
                        centerButton.addEventListener("click", () => {
                            try {
                                if (!pair(markerInput.value)) throw new Error("Сначала укажите метку объекта.");
                                centerInput.value = markerInput.value;
                                updateInputs();
                            } catch (error) { status.textContent = error.message; }
                        });
                    }
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
