/* Карты жилья: локальный OpenLayers, внешние тайлы только после нажатия. */
(() => {
    'use strict';
    document.addEventListener('DOMContentLoaded', () => {
        const root = document.querySelector('.info-map');
        const button = root?.querySelector('.info-map__load');
        if (!button) return;
        const canvas = root.querySelector('.info-map__canvas');
        const status = root.querySelector('.info-map__status');
        button.addEventListener('click', () => {
            let map;
            try {
                if (!window.ol) throw new Error('Не удалось загрузить карту. Используйте список объектов ниже.');
                const data = JSON.parse(document.getElementById('information-map-data').textContent);
                const features = data.points.map(point => new ol.Feature({
                    geometry: new ol.geom.Point(ol.proj.fromLonLat(point.coordinates.map(Number))), point
                }));
                const source = new ol.source.Vector({features, wrapX:false});
                const tiles = new ol.source.XYZ({url:data.tile_url, attributions:data.attribution, maxZoom:19});
                tiles.on('tileloaderror', () => { status.textContent = 'Подложка недоступна. Метки и список объектов доступны.'; });
                canvas.hidden = false;
                const popup = document.createElement('div');
                popup.className = 'info-map__popup';
                const overlay = new ol.Overlay({element:popup, positioning:'bottom-center', offset:[0,-12]});
                map = new ol.Map({target:canvas, layers:[new ol.layer.Tile({source:tiles}), new ol.layer.Vector({source,
                    style:new ol.style.Style({image:new ol.style.Circle({radius:7, fill:new ol.style.Fill({color:'#2878b8'}), stroke:new ol.style.Stroke({color:'#fff',width:2})})})})],
                    overlays:[overlay], view:new ol.View({maxZoom:19}),
                    controls:ol.control.defaults.defaults({attributionOptions:{collapsible:false}}),
                    interactions:ol.interaction.defaults.defaults({mouseWheelZoom:false})});
                map.getView().fit(source.getExtent(), {padding:[45,45,45,45], maxZoom:15});
                map.on('singleclick', event => {
                    const feature = map.forEachFeatureAtPixel(event.pixel, item => item, {hitTolerance:8});
                    popup.replaceChildren();
                    if (!feature) { overlay.setPosition(undefined); return; }
                    const point = feature.get('point');
                    const link = document.createElement('a'); link.href = point.url; link.textContent = point.title;
                    const address = document.createElement('p'); address.textContent = point.address;
                    const close = document.createElement('button'); close.type='button'; close.textContent='Закрыть';
                    close.addEventListener('click', () => overlay.setPosition(undefined));
                    popup.append(link, address, close); overlay.setPosition(feature.getGeometry().getCoordinates());
                });
                button.hidden = true;
            } catch (error) {
                if (map) map.setTarget(undefined);
                canvas.hidden = true; status.textContent = error.message;
            }
        });
    });
})();
