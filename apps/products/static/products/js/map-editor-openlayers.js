/* Координаты поля: долгота, широта. Проекция карты: Web Mercator. */
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
    const longlat = point => ol.proj.toLonLat(point);
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
                    if (!window.ol) throw new Error("Не удалось загрузить редактор. Координаты можно ввести вручную.");
                    const initialMarker = pair(markerInput.value);
                    const initialCenter = pair(centerInput.value) || initialMarker || [39.920664, 43.428032];
                    const view = new ol.View({center:ol.proj.fromLonLat(initialCenter), zoom:zoomValue(zoomInput.value), minZoom:0, maxZoom:19});
                    const tiles = new ol.source.XYZ({
                        url:root.dataset.tileUrl, attributions:root.dataset.tileAttribution,
                        attributionsCollapsible:false, maxZoom:19,
                        tileLoadFunction:(tile, url) => {
                            const image = tile.getImage();
                            image.referrerPolicy = "strict-origin-when-cross-origin";
                            image.src = url;
                        },
                    });
                    tiles.on("tileloaderror", () => { status.textContent = "Не удалось загрузить подложку карты. Координаты можно сохранить вручную."; });
                    const features = new ol.source.Vector({wrapX:false});
                    const marker = new ol.Feature();
                    marker.setStyle(new ol.style.Style({image:new ol.style.Circle({radius:9, fill:new ol.style.Fill({color:"#2878b8"}), stroke:new ol.style.Stroke({color:"#fff", width:3})})}));
                    const setMarker = coords => {
                        marker.setGeometry(coords ? new ol.geom.Point(ol.proj.fromLonLat(coords)) : undefined);
                        if (coords && !features.hasFeature(marker)) features.addFeature(marker);
                        if (!coords) features.removeFeature(marker);
                    };
                    setMarker(initialMarker);
                    canvas.hidden = false;
                    map = new ol.Map({target:canvas, view, layers:[new ol.layer.Tile({source:tiles, preload:0}), new ol.layer.Vector({source:features})],
                        controls:ol.control.defaults.defaults({attributionOptions:{collapsible:false}}),
                        interactions:ol.interaction.defaults.defaults({mouseWheelZoom:false, doubleClickZoom:false, altShiftDragRotate:false, pinchRotate:false}),
                    });
                    const translate = new ol.interaction.Translate({features:new ol.Collection([marker]), hitTolerance:6});
                    map.addInteraction(translate);
                    translate.on("translateend", () => { markerInput.value = longlat(marker.getGeometry().getCoordinates()).join(", "); });
                    map.on("singleclick", event => {
                        const coords = longlat(event.coordinate);
                        markerInput.value = coords.join(", ");
                        setMarker(coords);
                    });
                    let lastCenter = longlat(view.getCenter()), lastZoom = view.getZoom();
                    // View events are synchronous: manual changes can be suppressed without
                    // delayed moveend events overwriting the original coordinate strings.
                    const updateViewFields = () => {
                        const center = longlat(view.getCenter()), zoom = Math.round(view.getZoom());
                        if (center.some((number, i) => Math.abs(number - lastCenter[i]) > 1e-10)) centerInput.value = center.join(", ");
                        if (zoom !== lastZoom) zoomInput.value = String(zoom);
                        lastCenter = center; lastZoom = zoom;
                    };
                    let suppress = false;
                    view.on(["change:center", "change:resolution"], () => { if (!suppress) updateViewFields(); });
                    const updateInputs = () => {
                        try {
                            const coords = pair(markerInput.value);
                            const center = pair(centerInput.value) || coords || [39.920664, 43.428032];
                            const zoom = zoomValue(zoomInput.value);
                            setMarker(coords);
                            suppress = true;
                            view.setCenter(ol.proj.fromLonLat(center));
                            view.setZoom(zoom);
                            lastCenter = longlat(view.getCenter()); lastZoom = view.getZoom();
                            suppress = false;
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
                    if (map) { map.setTarget(null); map.dispose(); }
                    canvas.hidden = true;
                    status.textContent = error.message;
                }
            });
        });
    });
})();
