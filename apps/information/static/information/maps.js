/* Карты жилья: локальный OpenLayers, внешние тайлы только после нажатия. */
(() => {
    'use strict';
    document.addEventListener('DOMContentLoaded', () => {
        const root = document.querySelector('.info-map');
        const button = root?.querySelector('.info-map__load');
        if (!button) return;
        const canvas = root.querySelector('.info-map__canvas');
        const status = root.querySelector('.info-map__status');
        let data;
        try { data = JSON.parse(document.getElementById('information-map-data').textContent); }
        catch { status.textContent = 'Не удалось прочитать данные карты.'; return; }
        const filter = root.querySelector('.info-map__filter');
        const input = root.querySelector('#information-map-search');
        const type = root.querySelector('#information-map-type');
        const results = root.querySelector('.info-map__results');
        const fitButton = root.querySelector('.info-map__fit');
        const rows = [...root.querySelectorAll('.info-map__objects li[data-object-id]')];
        const normalize = value => String(value || '').normalize('NFKC').toLocaleLowerCase('ru').replaceAll('ё', 'е');
        const searchText = new Map(data.points.map(point => [point.id, normalize(point.title + ' ' + (point.address || ''))]));
        let visibleIds = new Set(data.points.map(point => point.id));
        let updateMap = () => {};
        const applyFilter = () => {
            const words = normalize(input?.value).trim().split(/\s+/).filter(Boolean);
            visibleIds = new Set(data.points.filter(point => (!type?.value || point.housing_type === type.value) && words.every(word => searchText.get(point.id).includes(word))).map(point => point.id));
            rows.forEach(row => { row.hidden = !visibleIds.has(Number(row.dataset.objectId)); });
            const objectList = root.querySelector('.info-map__objects');
            if ((words.length || type?.value) && objectList) objectList.open = true;
            if (results) results.textContent = 'Найдено: ' + visibleIds.size + ' из ' + data.points.length + (visibleIds.size ? '' : '. Измените запрос или сбросьте фильтры.');
            if (fitButton) fitButton.disabled = !visibleIds.size;
            updateMap();
        };
        if (filter && input) {
            filter.hidden = false;
            input.addEventListener('input', applyFilter);
            if (type) type.addEventListener('change', applyFilter);
            root.querySelector('.info-map__reset').addEventListener('click', () => { input.value = ''; if (type) type.value = ''; applyFilter(); input.focus(); });
            applyFilter();
        }
        button.addEventListener('click', () => {
            let map;
            try {
                if (!window.ol) throw new Error('Не удалось загрузить карту. Используйте список объектов ниже.');
                const features = data.points.map(point => new ol.Feature({
                    geometry: new ol.geom.Point(ol.proj.fromLonLat(point.coordinates.map(Number))), point
                }));
                const source = new ol.source.Vector({features:features.filter(feature => visibleIds.has(feature.get('point').id)), wrapX:false});
                const selected = features.find(feature => feature.get('point').id === data.selected_id);
                const clusters = new ol.source.Cluster({distance:40, source});
                const styles = new Map();
                const tiles = new ol.source.XYZ({url:data.tile_url, attributions:data.attribution, maxZoom:19});
                tiles.on('tileloaderror', () => { status.textContent = 'Подложка недоступна. Метки и список объектов доступны.'; });
                canvas.hidden = false;
                const popup = document.createElement('div');
                popup.className = 'info-map__popup';
                const overlay = new ol.Overlay({element:popup, positioning:'bottom-center', offset:[0,-12], autoPan:{animation:{duration:200}}});
                map = new ol.Map({target:canvas, layers:[new ol.layer.Tile({source:tiles}), new ol.layer.Vector({source:clusters,
                    style:feature => {
                        const count = feature.get('features').length;
                        if (!styles.has(count)) styles.set(count, new ol.style.Style({
                            image:new ol.style.Circle({radius:count > 1 ? 17 : 7,
                                fill:new ol.style.Fill({color:count > 1 ? '#087c85' : '#2878b8'}),
                                stroke:new ol.style.Stroke({color:'#fff',width:2})}),
                            text:count > 1 ? new ol.style.Text({text:String(count), font:'bold 13px sans-serif',
                                fill:new ol.style.Fill({color:'#fff'})}) : undefined,
                        }));
                        return styles.get(count);
                    }})],
                    overlays:[overlay], view:new ol.View({center:ol.proj.fromLonLat(data.points[0].coordinates.map(Number)), zoom:10, maxZoom:19}),
                    controls:ol.control.defaults.defaults({attributionOptions:{collapsible:false}}),
                    interactions:ol.interaction.defaults.defaults({mouseWheelZoom:false})});
                const showAll = () => {
                    overlay.setPosition(undefined);
                    if (!source.getFeatures().length) return;
                    map.getView().fit(source.getExtent(), {padding:[45,45,45,45], maxZoom:15});
                };
                const showPopup = (members, coordinates) => {
                    popup.replaceChildren();
                    members = [...members].sort((a,b) => Number(b.get('point').id === data.selected_id) - Number(a.get('point').id === data.selected_id));
                    const heading = document.createElement('p');
                    heading.textContent = members.length > 1 ? 'Объектов в группе: ' + members.length : 'Объект жилья';
                    const list = document.createElement('ul');
                    list.className = 'info-map__popup-list';
                    members.forEach(member => {
                        const point = member.get('point');
                        const item = document.createElement('li');
                        if (point.id === data.selected_id) {
                            item.className = 'info-map__selected-item';
                            const label = document.createElement('strong'); label.textContent = 'Выбранный объект';
                            item.append(label, document.createElement('br'));
                        }
                        const link = document.createElement('a'); link.href = point.url; link.textContent = point.title;
                        const address = document.createElement('p'); address.textContent = point.address;
                        const kind = document.createElement('p'); kind.className = 'info-map__type-label'; kind.textContent = point.housing_type_label || '';
                        item.append(link, kind, address); list.append(item);
                    });
                    const close = document.createElement('button'); close.type='button'; close.textContent='Закрыть';
                    close.addEventListener('click', () => overlay.setPosition(undefined));
                    popup.append(heading, close, list); overlay.setPosition(coordinates);
                };
                map.on('singleclick', event => {
                    const feature = map.forEachFeatureAtPixel(event.pixel, item => item, {hitTolerance:8});
                    if (!feature) { overlay.setPosition(undefined); return; }
                    const group = feature.get('features') || clusters.getFeatures().find(cluster => cluster.get('features').includes(feature))?.get('features') || [feature];
                    showPopup(group, feature.getGeometry().getCoordinates());
                });
                map.getView().on('change:resolution', () => overlay.setPosition(undefined));
                const allButton = root.querySelector('.info-map__all');
                if (allButton) { allButton.hidden = false; allButton.addEventListener('click', () => {
                    if (input) input.value = ''; if (type) type.value = ''; applyFilter(); showAll();
                }); }
                if (fitButton) { fitButton.hidden = false; fitButton.addEventListener('click', showAll); }
                const highlight = new ol.source.Vector();
                if (selected) {
                    map.addLayer(new ol.layer.Vector({source:highlight, zIndex:10,
                        style:new ol.style.Style({image:new ol.style.Circle({radius:22,
                            fill:new ol.style.Fill({color:'rgba(0,0,0,0)'}), stroke:new ol.style.Stroke({color:'#b33b16',width:3})})})}));
                }
                updateMap = () => {
                    overlay.setPosition(undefined);
                    source.clear(true); source.addFeatures(features.filter(feature => visibleIds.has(feature.get('point').id)));
                    highlight.clear(true);
                    if (selected && visibleIds.has(selected.get('point').id)) highlight.addFeature(selected);
                };
                updateMap();
                if (selected && visibleIds.has(selected.get('point').id)) {
                    map.getView().setCenter(selected.getGeometry().getCoordinates()); map.getView().setZoom(16);
                    map.renderSync();
                    showPopup([selected], selected.getGeometry().getCoordinates());
                } else { showAll(); }
                button.hidden = true;
            } catch (error) {
                updateMap = () => {};
                if (map) map.setTarget(undefined);
                canvas.hidden = true; status.textContent = error.message;
            }
        });
    });
})();
