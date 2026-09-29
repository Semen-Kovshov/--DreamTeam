# Промпты для генерации арта

Полный набор изображений по контракту ассетов (`docs/06-ui-spec.md` §4,
дизайн-комплект «хвоя»): 4 фона сцен + 16 спрайтов (4 персонажа × 4 эмоции)
+ фирменный знак. Карточки каталога и портрет брифа отдельного арта не
требуют — интерфейс сам кропит фоны сцен и спрайты `calm`.

Промпты на английском (генераторы понимают его стабильнее), русские подписи —
что это и куда класть. Рабочий процесс и негативный промпт — в конце.

---

## 0. Общий стилевой блок (добавлять к каждому промпту)

```text
professional business light-novel illustration, semi-realistic digital painting,
clean confident linework, soft cinematic lighting, muted warm palette with deep
pine-teal accents (#1f7a6f), respectful adult tone, high detail, no anime
exaggeration
```

Негативный промпт (для всех изображений):

```text
anime chibi, exaggerated expressions, oversaturated neon colors, readable text,
letters, numbers, watermark, signature, logo, lens flare, harsh shadows,
cluttered composition, distorted hands, extra fingers
```

---

## 1. Фоны сцен — 4 шт.

Файлы: `frontend/public/scenes/<id>.jpg`, **1920×1080** (генерировать 16:9),
JPG q80, ≤400 КБ. Общие требования зашиты в промпты: нижняя треть спокойная
(её закрывает диалоговое окно), центр свободен под персонажа, без людей и
читаемого текста; сверху код кладёт виньетку — нужен запас по контрасту.

### 1.1 `scenes/salary.jpg` — переговорная IT-компании (Ирина)

```text
Empty modern IT-company meeting room in the evening, floor-to-ceiling glass
wall with a blurred open-space office behind it, whiteboard with wiped-off
unreadable diagram traces, single long table edge in the blurred foreground,
warm city lights outside the window, soft teal-and-amber color harmony,
late-quarter working atmosphere, empty room, no people, center of the frame
open and uncluttered, bottom third of the frame is a calm dark table surface
with soft gradient, shallow depth of field, wide shot, 16:9
```

### 1.2 `scenes/supplier.jpg` — офис-цех обжарщика кофе (Сергей)

```text
Empty coffee roastery office-showroom, warm wood panel walls, burlap sacks of
green coffee beans stacked along the side, vintage brass coffee roaster machine
in the blurred background, dust motes in warm daylight beams from tall
industrial windows, wooden desk edge in the blurred foreground, cozy craft
atmosphere with amber and deep-brown tones and a subtle pine-teal accent,
empty room, no people, center of the frame open, bottom third calm and dark,
shallow depth of field, wide shot, 16:9
```

### 1.3 `scenes/discount.jpg` — кабинет операционного директора клиента (Марина)

```text
Empty bright modern executive office by a large window, soft overcast daylight,
light-grey and warm-beige tones with gentle green plant accents, shelf with
unlabeled binders, small potted plants on the windowsill, glass partition with
a blurred quiet open space behind, tidy desk edge in the blurred foreground,
calm videocall-meeting atmosphere, no monitors facing the viewer, empty room,
no people, center of the frame open, bottom third calm, shallow depth of
field, wide shot, 16:9
```

### 1.4 `scenes/rent.jpg` — кабинет владельца бизнес-центра (Аркадий Петрович)

```text
Empty old-fashioned solid director office in a class-B business center, massive
dark wooden desk edge in the blurred foreground, venetian blinds casting warm
horizontal light stripes, wall with framed unreadable certificates and old
photographs, leather chair, worn oriental rug, a small safe in the corner,
respectable slightly dated atmosphere, warm ochre and deep-green tones, empty
room, no people, center of the frame open, bottom third calm and dark, shallow
depth of field, wide shot, 16:9
```

---

## 2. Спрайты персонажей — 16 шт.

Файлы: `frontend/public/sprites/<id>/<mood>.png`, **900×1200** (генерировать
3:4), PNG с прозрачностью (генерировать на ровном светло-сером фоне и
вырезать), по пояс, руки на уровне стола, низ кадра = линия стола.

**Как держать консистентность.** Для каждого персонажа: сгенерировать `calm`,
добиться нужного образа, затем остальные три эмоции — тем же сидом + референсом
персонажа (Midjourney `--cref`, SDXL IP-Adapter, Flux Redux) или img2img с
малым denoise; в промпте меняется ТОЛЬКО блок «EMOTION». Поза, свет и одежда
между эмоциями не меняются — переключение в интерфейсе мгновенное.

Общий каркас спрайта (общий для всех, вставлять после блока стиля):

```text
waist-up portrait of a single character, standing behind a table, hands visible
at table level, three-quarter view facing the viewer, soft warm key light from
the upper left matching an office interior, subtle rim light, flat light-grey
studio background for easy cutout, sharp focus on the face, consistent
character sheet style, 3:4
```

Блоки эмоций (подставлять в `EMOTION:`; формулировки одинаковые для всех
персонажей — характер задаёт описание самого персонажа):

- **calm** — `neutral attentive business expression, relaxed shoulders, slight polite head tilt, hands resting calmly on the table`
- **pleased** — `warm restrained half-smile, softened eyebrows, open palm gesture, slight approving nod, welcoming posture`
- **tense** — `pressed lips, drawn eyebrows, guarded look aside, arms crossed or fingers interlocked on the table, torso leaning slightly back`
- **angry** — `hard direct stare, tightened jaw, one palm firmly on the table, torso leaning slightly forward, controlled professional anger, no shouting`

### 2.1 `sprites/salary/<mood>.png` — Ирина, руководитель отдела продуктов

Постоянное описание персонажа:

```text
CHARACTER: russian businesswoman around 40, shoulder-length ash-brown hair
tucked behind one ear, thin silver-framed glasses, tailored slate-blue blazer
over a white blouse, small stud earrings, no other jewelry, tired ironic
intelligence in her eyes, dry composed manner
EMOTION: <вставить блок эмоции>
```

### 2.2 `sprites/supplier/<mood>.png` — Сергей, коммерческий директор обжарщика

```text
CHARACTER: burly russian man around 45, short dark beard with first grey
strands, weathered confident face, rolled-up sleeves of a checkered
flannel shirt, dark-brown waxed canvas work apron with brass hardware,
strong hands of a craftsman, energetic pushy presence
EMOTION: <вставить блок эмоции>
```

### 2.3 `sprites/discount/<mood>.png` — Марина, операционный директор клиента

```text
CHARACTER: soft-featured russian woman around 35, chestnut hair in a loose low
bun with strands framing the face, beige knitted cardigan over a light silk
blouse, thin gold chain necklace, gentle apologetic politeness, conflict-avoidant
warmth in her posture
EMOTION: <вставить блок эмоции>
```

Нюанс для `angry`: у Марины «на взводе» — не гнев, а тихая обида; можно смягчить
блок: `hurt withdrawn look, lips pressed, arms wrapped around herself, turned
slightly away, quiet offended dignity instead of open anger`.

### 2.4 `sprites/rent/<mood>.png` — Аркадий Петрович, владелец бизнес-центра

```text
CHARACTER: solid russian man around 60, grey hair combed back, neat grey
moustache, deep paternal squint wrinkles, brown tweed vest over a checked
shirt without a tie, reading glasses hanging on a cord on his chest, thick
reliable hands, thrifty patriarchal presence
EMOTION: <вставить блок эмоции>
```

---

## 3. Фирменный знак (favicon) — 1 шт.

Замена 🤝 в `frontend/index.html`, 32×32 (генерировать крупно, уменьшить).

```text
minimal flat vector logo mark, two abstract speech-bubble arcs meeting in the
middle over a horizontal table line, forming a subtle handshake silhouette in
the negative space, single deep pine-teal color #1f7a6f on white background,
geometric, balanced, crisp at small sizes, no text, app icon style
```

---

## 4. Рабочий процесс

1. **Сцены**: генерация 16:9 → даунскейл до 1920×1080 → JPG q80; если >400 КБ —
   пережать (squoosh.app). Положить в `frontend/public/scenes/`.
2. **Спрайты**: `calm` до попадания в образ → остальные эмоции тем же
   сидом/референсом → вырезать фон (Photoshop / remove.bg / rembg) → кадр
   900×1200, персонаж по центру, обрез по пояс у нижней кромки → PNG с альфой
   в `frontend/public/sprites/<id>/`.
3. Пересборка не нужна: файлы подхватываются интерфейсом сразу (обновить
   страницу). До поставки арта работают плейсхолдеры — можно отдавать частями,
   например только `calm` каждого персонажа: остальные эмоции откатятся на
   плейсхолдер до готовности.
4. Проверка эмоций в бою: грубость в чате доводит персонажа до `tense`/`angry`,
   кофе и вопросы возвращают `pleased` (чек-лист приёмки дизайна, §10).
