/* Leaflet использует latlng; поля и импорт сохраняют Joomla longlat. */
(() => {
    "use strict";
    const pair = value => {
        if (!String(value || "").trim()) return null;
        const parts = String(value).split(",");
        if (parts.length !== 2 || parts.some(part => !part.trim())) throw new Error("Введите долготу и широту через запятую.");
        const result = parts.map(Number);
        if (!result.every(Number.isFinite) || Math.abs(result[0]) > 180 || Math.abs(result[1]) > 90) throw new Error("Проверьте диапазон координат.");
        return result;
    };
    const zoomValue = value => {
        const number = String(value).trim() === "" ? 12 : Number(value);
        if (!Number.isInteger(number) || number < 0 || number > 19) throw new Error("Масштаб должен быть целым числом от 0 до 19.");
        return number;
    };
    const latlng = coords => [coords[1], coords[0]];
    const longlat = point => [point.lng >= -180 && point.lng <= 180 ? point.lng : point.wrap().lng, point.lat];
    document.addEventListener("DOMContentLoaded", () => {
        document.querySelectorAll("[data-object-map-editor]").forEach(root => {
            const markerInput = document.getElementById(root.dataset.markerInput);
            const centerInput = document.getElementById(root.dataset.centerInput);
            const zoomInput = document.getElementById(root.dataset.zoomInput);
            const canvas = root.querySelector(".object-map__canvas");
            const button = root.querySelector(".object-map__load");
            const centerButton = root.querySelector(".object-map__center");
            const status = root.querySelector(".object-map__status");
            if (!markerInput || !centerInput || !zoomInput) return;
            button.addEventListener("click", () => {
                let map;
                try {
                    if (!window.L) throw new Error("Не удалось загрузить редактор. Координаты можно ввести вручную.");
                    const initialMarker = pair(markerInput.value);
                    const initialCenter = pair(centerInput.value) || initialMarker || [39.920664, 43.428032];
                    const initialZoom = zoomValue(zoomInput.value);
                    canvas.hidden = false;
                    map = L.map(canvas, {scrollWheelZoom:false, minZoom:0, maxZoom:19, zoomAnimation:false, fadeAnimation:false});
                    map.setView(latlng(initialCenter), initialZoom);
                    const tiles = L.tileLayer(root.dataset.tileUrl, {
                        maxZoom:19, attribution:root.dataset.tileAttribution,
                        referrerPolicy:"strict-origin-when-cross-origin", updateWhenIdle:true,
                    });
                    tiles.on("tileerror", () => { status.textContent = "Не удалось загрузить подложку карты. Координаты можно сохранить вручную."; });
                    tiles.addTo(map);
                    let marker, suppress = false;
                    const setMarker = coords => {
                        if (!coords) { if (marker) marker.remove(); marker = null; return; }
                        if (marker) { marker.setLatLng(latlng(coords)); return; }
                        marker = L.marker(latlng(coords), {draggable:true, autoPan:false}).addTo(map);
                        marker.on("dragend", () => { markerInput.value = longlat(marker.getLatLng()).join(", "); });
                    };
                    setMarker(initialMarker);
                    let lastCenter = longlat(map.getCenter()), lastZoom = map.getZoom();
                    map.on("click", event => {
                        const coords = longlat(event.latlng);
                        markerInput.value = coords.join(", ");
                        setMarker(coords);
                    });
                    map.on("moveend zoomend", () => {
                        const center = longlat(map.getCenter()), zoom = map.getZoom();
                        if (!suppress) {
                            if (center.some((number, i) => Math.abs(number - lastCenter[i]) > 1e-10)) centerInput.value = center.join(", ");
                            if (zoom !== lastZoom) zoomInput.value = String(zoom);
                        }
                        lastCenter = center; lastZoom = zoom;
                    });
                    const updateInputs = () => {
                        try {
                            const coords = pair(markerInput.value);
                            const center = pair(centerInput.value) || coords || [39.920664, 43.428032];
                            const zoom = zoomValue(zoomInput.value);
                            setMarker(coords);
                            suppress = true;
                            map.setView(latlng(center), zoom, {animate:false});
                            suppress = false;
                            lastCenter = longlat(map.getCenter()); lastZoom = map.getZoom();
                            status.textContent = "";
                        } catch (error) { suppress = false; status.textContent = error.message; }
                    };
                    [markerInput, centerInput, zoomInput].forEach(input => input.addEventListener("change", updateInputs));
                    centerButton.hidden = false;
                    centerButton.addEventListener("click", () => {
                        try {
                            if (!pair(markerInput.value)) throw new Error("Сначала укажите метку объекта.");
                            centerInput.value = markerInput.value;
                            updateInputs();
                        } catch (error) { status.textContent = error.message; }
                    });
                    button.hidden = true;
                    status.textContent = "";
                } catch (error) {
                    if (map) map.remove();
                    canvas.hidden = true;
                    status.textContent = error.message;
                }
            });
        });
    });
})();
