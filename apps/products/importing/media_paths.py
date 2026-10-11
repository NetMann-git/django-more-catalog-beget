"""Явно проверенные дополнительные файлы старых карточек Joomla."""
import re

EXTRA_MEDIA = {
    910: {'images/stories/gagra.jpg'},
    204: {'images/stories/noi.jpg'},
    192: {
        'images/ikonki/ducsh.png', 'images/ikonki/hol.png',
        'images/ikonki/kon.png', 'images/ikonki/kux.png', 'images/ikonki/vod.png',
    },
}


def valid_media_path(path, item_id):
    """Разрешить папки uploads и точные дополнительные пути для данного ID."""
    return bool(re.fullmatch(
        r'images/uploads/user_[0-9]+/[\w .()-]+\.(jpg|jpeg|png|webp|gif|mp4)', path, flags=re.I,
    )) or path in EXTRA_MEDIA.get(item_id, set())
