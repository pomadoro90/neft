"""
oil_pump_jack.py
================
Blender 3.x / 4.x Python script — генерирует реалистичную 3D-модель
нефтяного станка-качалки (API pump jack / «кивающий осёл»).

Запуск: открыть Blender → Scripting → вставить этот файл → Run Script
        или из терминала:
            blender --background --python oil_pump_jack.py

Компоненты:
  1. Бетонное основание
  2. Сальниковая рама (base skid) — стальные I-балки
  3. Стойка Сэмпсона (A-образная рама)
  4. Балансирная балка (walking beam, два параллельных I-профиля)
  5. Головка (horsehead, дуговая кривая)
  6. Бриделин + хомут полированной штанги
  7. Редуктор (gearbox)
  8. Кривошипы + противовесы (cranks / counterweights)
  9. Шатуны (pitman arms) + траверса (equalizer bar)
 10. Электродвигатель + клиноремённая передача
 11. Устьевое оборудование (wellhead / christmas tree)
 12. Ограждения, платформа, лестница, поручни
 13. Освещение + камера + настройки рендера

Все размеры — метры, прототип: API Unit 114D (средний промысловый станок).
"""

import bpy
import math

# ============================================================
# УТИЛИТЫ
# ============================================================

def clear_scene():
    """Удалить всё из сцены и очистить orphan-данные."""
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for blk in bpy.data.meshes:
        if blk.users == 0:
            bpy.data.meshes.remove(blk)
    for blk in bpy.data.materials:
        if blk.users == 0:
            bpy.data.materials.remove(blk)
    print("[clear_scene] Сцена очищена.")


def new_mat(name, rgb, metallic=0.7, roughness=0.35):
    """Создать Principled BSDF материал."""
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    out  = nodes.new('ShaderNodeOutputMaterial')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1.0)
    bsdf.inputs['Metallic'].default_value   = metallic
    bsdf.inputs['Roughness'].default_value  = roughness
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat


def set_mat(obj, mat):
    """Назначить материал объекту."""
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)


def box(name, cx, cy, cz, lx, ly, lz, mat=None):
    """Создать параллелепипед с центром (cx,cy,cz) и размерами lx×ly×lz."""
    bpy.ops.mesh.primitive_cube_add(location=(cx, cy, cz))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (lx / 2, ly / 2, lz / 2)
    bpy.ops.object.transform_apply(scale=True)
    if mat:
        set_mat(obj, mat)
    return obj


def cyl(name, cx, cy, cz, r, depth, rot=(0, 0, 0), mat=None, verts=20):
    """Создать цилиндр."""
    bpy.ops.mesh.primitive_cylinder_add(
        radius=r, depth=depth,
        location=(cx, cy, cz),
        rotation=rot,
        vertices=verts,
    )
    obj = bpy.context.active_object
    obj.name = name
    if mat:
        set_mat(obj, mat)
    return obj


def angled_box(name, x1, z1, x2, z2, y_center, width_y, thick_x, mat=None):
    """
    Создать прямоугольный брус, ориентированный вдоль вектора (x1,z1)->(x2,z2).
    width_y  — размер поперёк (по Y),
    thick_x  — толщина поперечного сечения.
    """
    dx = x2 - x1
    dz = z2 - z1
    length = math.sqrt(dx * dx + dz * dz)
    cx = (x1 + x2) / 2
    cz = (z1 + z2) / 2
    angle_y = math.atan2(dx, dz)          # поворот вокруг оси Y

    bpy.ops.mesh.primitive_cube_add(location=(cx, y_center, cz))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (thick_x / 2, width_y / 2, length / 2)
    bpy.ops.object.transform_apply(scale=True)
    obj.rotation_euler = (0, angle_y, 0)
    bpy.ops.object.transform_apply(rotation=True)
    if mat:
        set_mat(obj, mat)
    return obj


def collect(obj, col):
    """Переместить объект из корневой коллекции в col."""
    try:
        bpy.context.scene.collection.objects.unlink(obj)
    except Exception:
        pass
    col.objects.link(obj)


# ============================================================
# КОНСТАНТЫ РАЗМЕРОВ (метры, API Unit 114D)
# ============================================================

# Ось X — вдоль станка (+ к головке), Y — поперёк, Z — вертикаль

PIVOT_X = 0.0          # X центра шарнира балансира
PIVOT_Z = 4.20         # высота шарнира балансира

BEAM_FRONT = 2.80      # длина балки перед шарниром (к головке)
BEAM_REAR  = 3.80      # длина балки за шарниром (к хвосту)
BEAM_Y     = 0.72      # Y-смещение каждой из двух параллельных балок
BEAM_WEB_W = 0.10      # толщина стенки I-профиля
BEAM_H     = 0.26      # высота I-профиля
FLANGE_W   = 0.22      # ширина полки I-профиля
FLANGE_T   = 0.04      # толщина полки

HH_TIP_X = PIVOT_X + BEAM_FRONT  # X конца балки / основания головки
HH_R     = 0.88        # радиус дуги головки
HH_SEGS  = 18          # сегментов дуги
HH_ARC   = 0.72 * math.pi  # угол охвата дуги (~130°)

SP_BASE_Y = 0.90       # Y-полуширина основания стойки Сэмпсона
SP_TOP_Y  = 0.12       # Y-полуширина вершины
SP_LEG_W  = 0.16       # ширина сечения ноги
SP_LEG_D  = 0.22       # глубина сечения ноги

GB_X   = PIVOT_X - 2.75  # X центра редуктора
GB_Z   = 0.95             # Z центра редуктора (приподнят, чтобы кривошип не задевал землю)
GB_W   = 1.15             # длина корпуса редуктора (X)
GB_D   = 1.05             # ширина корпуса (Y)
GB_H   = 0.95             # высота корпуса (Z)

CRANK_Z  = GB_Z + 0.05    # Z оси кривошипа (= 1.00)
CRANK_R  = 0.70           # радиус кривошипа (нижняя точка ≈ 0.30 — над рамой)
CRANK_ANG = math.radians(22)   # статический угол кривошипа
CRANK_PIN_X = GB_X + CRANK_R * math.sin(CRANK_ANG)
CRANK_PIN_Z = CRANK_Z + CRANK_R * math.cos(CRANK_ANG)

EQ_X = PIVOT_X - BEAM_REAR + 0.70   # X траверсы (equalizer)
# Траверса висит чуть ниже нижней полки балки, чтобы шатуны не пересекали балку
EQ_Z = PIVOT_Z - BEAM_H / 2 - FLANGE_T - 0.08

MOTOR_X = GB_X + 2.30   # X центра электродвигателя
MOTOR_Z = 0.52

BASE_LEN = 10.50        # длина рамы
BASE_W   = 2.60         # ширина рамы
BASE_H   = 0.18         # высота рамы

WH_X = HH_TIP_X        # X устья скважины

# Глобальные точки подвеса (вычисляются в build_horsehead)
BRIDLE_TOP_X = HH_TIP_X
BRIDLE_TOP_Z = PIVOT_Z - HH_R


# ============================================================
# МАТЕРИАЛЫ
# ============================================================

def build_materials():
    """Создать все материалы, вернуть словарь."""
    print("[materials] Создаю материалы...")
    M = {}
    M['steel']      = new_mat('M_Steel',      (0.58, 0.58, 0.60), metallic=0.95, roughness=0.15)
    M['dark_steel'] = new_mat('M_DarkSteel',  (0.18, 0.18, 0.20), metallic=0.90, roughness=0.28)
    M['paint_gray'] = new_mat('M_PaintGray',  (0.38, 0.40, 0.42), metallic=0.05, roughness=0.55)
    M['paint_red']  = new_mat('M_PaintRed',   (0.62, 0.07, 0.07), metallic=0.05, roughness=0.50)
    M['yellow']     = new_mat('M_Yellow',     (0.90, 0.76, 0.02), metallic=0.05, roughness=0.50)
    M['black']      = new_mat('M_Black',      (0.04, 0.04, 0.04), metallic=0.15, roughness=0.75)
    M['rust']       = new_mat('M_Rust',       (0.44, 0.19, 0.07), metallic=0.15, roughness=0.85)
    M['concrete']   = new_mat('M_Concrete',   (0.60, 0.57, 0.53), metallic=0.00, roughness=0.92)
    M['ground']     = new_mat('M_Ground',     (0.27, 0.21, 0.14), metallic=0.00, roughness=0.98)
    print(f"[materials] Создано {len(M)} материалов.")
    return M


# ============================================================
# 1. ФУНДАМЕНТ + РАМА (base skid)
# ============================================================

def build_base(col, M):
    """Бетонная плита + сальниковая сварная рама из I-балок."""
    print("[base] Строю фундамент и раму...")

    # Бетонная плита
    collect(box('Foundation', PIVOT_X, 0, -0.15,
                BASE_LEN + 1.8, BASE_W + 1.8, 0.30, M['concrete']), col)

    # Земля
    bpy.ops.mesh.primitive_plane_add(size=50, location=(0, 0, -0.01))
    g = bpy.context.active_object
    g.name = 'Ground'
    set_mat(g, M['ground'])
    # Ground не идёт в коллекцию станка

    # 2 продольные I-балки рамы
    for tag, y in (('L', BASE_W / 2 - 0.15), ('R', -(BASE_W / 2 - 0.15))):
        # стенка
        collect(box(f'Skid_Web_{tag}', PIVOT_X, y, BASE_H / 2,
                    BASE_LEN, 0.12, BASE_H, M['dark_steel']), col)
        # верхняя полка
        collect(box(f'Skid_TFlg_{tag}', PIVOT_X, y, BASE_H - 0.02,
                    BASE_LEN, 0.30, FLANGE_T, M['dark_steel']), col)
        # нижняя полка
        collect(box(f'Skid_BFlg_{tag}', PIVOT_X, y, 0.02,
                    BASE_LEN, 0.30, FLANGE_T, M['dark_steel']), col)

    # Поперечные балки (шпалы)
    for i, xp in enumerate([-4.2, -3.0, -1.7, -0.4, 0.5, 1.8, 3.6]):
        collect(box(f'Skid_Cross_{i}', xp, 0, BASE_H / 2,
                    0.12, BASE_W - 0.10, BASE_H - 0.04, M['dark_steel']), col)

    # Торцевые заглушки
    collect(box('Skid_End_F',  3.9, 0, BASE_H / 2,
                0.14, BASE_W + 0.10, BASE_H, M['dark_steel']), col)
    collect(box('Skid_End_R', -4.6, 0, BASE_H / 2,
                0.14, BASE_W + 0.10, BASE_H, M['dark_steel']), col)

    print("[base] Рама готова.")


# ============================================================
# 2. СТОЙКА СЭМПСОНА (Sampson post / A-frame)
# ============================================================

def build_sampson(col, M):
    """A-образная рама, несущая шарнир балансирной балки."""
    print("[sampson] Строю стойку Сэмпсона...")

    z_bot = BASE_H
    z_top = PIVOT_Z

    for tag, sign in (('L', 1), ('R', -1)):
        y_bot = sign * SP_BASE_Y
        y_top = sign * SP_TOP_Y

        # Длина ноги
        dy = y_top - y_bot
        dz = z_top - z_bot
        length = math.sqrt(dy * dy + dz * dz)
        cy = (y_bot + y_top) / 2
        cz = (z_bot + z_top) / 2
        angle_x = math.atan2(-dy, dz)   # наклон вокруг X

        # Стенка I-ноги
        bpy.ops.mesh.primitive_cube_add(location=(PIVOT_X, cy, cz))
        leg = bpy.context.active_object
        leg.name = f'SP_Leg_{tag}'
        leg.scale = (SP_LEG_W / 2, SP_LEG_D / 2, length / 2)
        bpy.ops.object.transform_apply(scale=True)
        leg.rotation_euler = (angle_x, 0, 0)
        bpy.ops.object.transform_apply(rotation=True)
        set_mat(leg, M['paint_gray'])
        collect(leg, col)

        # Полки I-ноги (имитация двутавра)
        for fx in (SP_LEG_W * 1.6,):
            bpy.ops.mesh.primitive_cube_add(location=(PIVOT_X, cy, cz))
            flg = bpy.context.active_object
            flg.name = f'SP_LegFlg_{tag}'
            flg.scale = (fx / 2, SP_LEG_D * 0.20 / 2, length / 2)
            bpy.ops.object.transform_apply(scale=True)
            flg.rotation_euler = (angle_x, 0, 0)
            bpy.ops.object.transform_apply(rotation=True)
            set_mat(flg, M['paint_gray'])
            collect(flg, col)

    # Горизонтальные раскосы (на трёх уровнях)
    for h in (1.0, 2.0, 3.1):
        t = (h - z_bot) / (z_top - z_bot)
        y_h = SP_BASE_Y + (SP_TOP_Y - SP_BASE_Y) * t
        collect(box(f'SP_HBrace_{h:.1f}', PIVOT_X, 0, h,
                    SP_LEG_W, y_h * 2 + SP_LEG_D, 0.12, M['paint_gray']), col)

    # X-образные диагонали
    pairs = [(1.0, 2.0), (2.0, z_top)]
    for pi, (za, zb) in enumerate(pairs):
        ta = (za - z_bot) / (z_top - z_bot)
        tb = (zb - z_bot) / (z_top - z_bot)
        ya = SP_BASE_Y + (SP_TOP_Y - SP_BASE_Y) * ta
        yb = SP_BASE_Y + (SP_TOP_Y - SP_BASE_Y) * tb
        for di, (y1, y2) in enumerate(((ya, -yb), (-ya, yb))):
            dy = y2 - y1
            dz = zb - za
            le = math.sqrt(dy * dy + dz * dz)
            bpy.ops.mesh.primitive_cube_add(location=(PIVOT_X, (y1 + y2) / 2, (za + zb) / 2))
            xb = bpy.context.active_object
            xb.name = f'SP_XBrace_{pi}_{di}'
            xb.scale = (0.05, 0.05, le / 2)
            bpy.ops.object.transform_apply(scale=True)
            xb.rotation_euler = (math.atan2(-dy, dz), 0, 0)
            bpy.ops.object.transform_apply(rotation=True)
            set_mat(xb, M['steel'])
            collect(xb, col)

    # Шапка стойки + опорный вал шарнира
    collect(box('SP_Cap', PIVOT_X, 0, PIVOT_Z + 0.22,
                0.48, 0.75, 0.44, M['dark_steel']), col)
    collect(cyl('SP_PivotShaft', PIVOT_X, 0, PIVOT_Z,
                0.078, BEAM_Y * 2 + 0.90, (math.pi / 2, 0, 0), M['steel']), col)

    print("[sampson] Стойка готова.")


# ============================================================
# 3. БАЛАНСИРНАЯ БАЛКА (walking beam)
# ============================================================

def build_beam(col, M):
    """Два параллельных I-профиля + поперечные диафрагмы."""
    print("[beam] Строю балансирную балку...")

    total = BEAM_FRONT + BEAM_REAR
    cx    = PIVOT_X + (BEAM_FRONT - BEAM_REAR) / 2   # центр по X

    for tag, y in (('L', BEAM_Y), ('R', -BEAM_Y)):
        # Стенка
        collect(box(f'Beam_Web_{tag}',    cx, y, PIVOT_Z,
                    total, BEAM_WEB_W, BEAM_H, M['paint_gray']), col)
        # Верхняя полка
        collect(box(f'Beam_TFlg_{tag}',   cx, y, PIVOT_Z + BEAM_H / 2,
                    total, FLANGE_W, FLANGE_T, M['paint_gray']), col)
        # Нижняя полка
        collect(box(f'Beam_BFlg_{tag}',   cx, y, PIVOT_Z - BEAM_H / 2,
                    total, FLANGE_W, FLANGE_T, M['paint_gray']), col)

    # Поперечные диафрагмы через каждый ~1 м
    for i, xp in enumerate([
        PIVOT_X,
        PIVOT_X + 1.0, PIVOT_X + 2.2,
        PIVOT_X - 1.0, PIVOT_X - 2.2, PIVOT_X - 3.4,
    ]):
        collect(box(f'Beam_Diaphragm_{i}', xp, 0, PIVOT_Z,
                    0.06, BEAM_Y * 2, BEAM_H + 0.04, M['steel']), col)

    print("[beam] Балка готова.")


# ============================================================
# 4. ГОЛОВКА (horsehead)
# ============================================================

def build_horsehead(col, M):
    """
    Головка балансира («horsehead»).
    Полудисковая форма перед концом балки:
      центр дуги  = (HH_TIP_X, PIVOT_Z) — на оси балки в её носу
      радиус       = HH_R
      дуга 180°    — от верха (12 ч) ПО ЧАСОВОЙ через перед (3 ч) в низ (6 ч)
    Низ дуги — точка подвеса бриделя; кабель висит вертикально.
    """
    print("[horsehead] Строю головку...")

    arc_cx = HH_TIP_X
    arc_cz = PIVOT_Z

    ang_start = math.pi / 2     # верх (12 ч)
    arc_span  = math.pi          # 180°  (по часовой стрелке)

    seg_arc = arc_span / HH_SEGS
    seg_len = HH_R * seg_arc * 1.18

    for i in range(HH_SEGS):
        t = (i + 0.5) / HH_SEGS
        angle = ang_start - t * arc_span     # по часовой → угол убывает

        sx = arc_cx + HH_R * math.cos(angle)
        sz = arc_cz + HH_R * math.sin(angle)

        tang = angle - math.pi / 2          # касательная к окружности

        # Боковые рёбра дуги (две параллельные пластины-обода)
        for tag, y in (('L', BEAM_Y), ('R', -BEAM_Y)):
            bpy.ops.mesh.primitive_cube_add(location=(sx, y, sz))
            seg = bpy.context.active_object
            seg.name = f'HH_Rim_{i}_{tag}'
            seg.scale = (seg_len / 2, 0.08 / 2, 0.26 / 2)
            bpy.ops.object.transform_apply(scale=True)
            seg.rotation_euler = (0, tang, 0)
            bpy.ops.object.transform_apply(rotation=True)
            set_mat(seg, M['dark_steel'])
            collect(seg, col)

        # Поперечные рёбра жёсткости (каждые 3 сегмента + первый/последний)
        if i % 3 == 0 or i == HH_SEGS - 1 or i == 0:
            collect(box(f'HH_Cross_{i}', sx, 0, sz,
                        0.06, BEAM_Y * 2, 0.22, M['dark_steel']), col)

    # === Силовая обшивка / задний веб (вертикальная стенка от верха к низу дуги
    #     по линии носа балки — закрывает «букву D») ===
    for tag, y in (('L', BEAM_Y - 0.02), ('R', -(BEAM_Y - 0.02))):
        collect(box(f'HH_Web_{tag}', arc_cx, y, arc_cz,
                    0.10, 0.05, 2 * HH_R, M['paint_gray']), col)

    # Диагональный раскос внутри головки (имитация фермы)
    diag_top_x  = arc_cx + HH_R * math.cos(math.radians(60))   # ~верх-перёд
    diag_top_z  = arc_cz + HH_R * math.sin(math.radians(60))
    diag_bot_x  = arc_cx + HH_R * math.cos(math.radians(-60))  # ~низ-перёд
    diag_bot_z  = arc_cz + HH_R * math.sin(math.radians(-60))
    collect(angled_box('HH_Truss',
                       diag_top_x, diag_top_z, diag_bot_x, diag_bot_z,
                       0, BEAM_Y * 2 - 0.05, 0.05, M['steel']), col)

    # === Шкив (sheave) в нижней точке дуги — кабель катится по нему ===
    sheave_x = arc_cx + HH_R * math.cos(-math.pi / 2)   # = arc_cx
    sheave_z = arc_cz + HH_R * math.sin(-math.pi / 2)   # = PIVOT_Z - HH_R
    collect(cyl('HH_Sheave', sheave_x, 0, sheave_z,
                0.11, BEAM_Y * 2 + 0.40,
                (math.pi / 2, 0, 0), M['steel'], verts=24), col)

    # Сохраняем точку подвеса для функции бриделя
    global BRIDLE_TOP_X, BRIDLE_TOP_Z
    BRIDLE_TOP_X = sheave_x
    BRIDLE_TOP_Z = sheave_z

    print(f"[horsehead] Готово. Точка подвеса: x={sheave_x:.2f}, z={sheave_z:.2f}")


# ============================================================
# 5. БРИДЕЛЬ + ХОМУТ ПОЛИРОВАННОЙ ШТАНГИ
# ============================================================

def build_bridle(col, M):
    """Тросы бриделя, хомут-подвеска и полированная штанга.
       Висят от шкива в низу головки (BRIDLE_TOP_*).
       Идут вниз к устью скважины."""
    print("[bridle] Строю бридель...")

    top_x = BRIDLE_TOP_X
    top_z = BRIDLE_TOP_Z
    carrier_z = top_z - 1.05      # хомут на 1 м ниже шкива
    carrier_x = top_x

    # Хомут полированной штанги
    collect(box('Carrier_Body',    carrier_x, 0, carrier_z,
                0.09, 0.58, 0.24, M['steel']), col)
    collect(box('Carrier_Clamp_T', carrier_x, 0, carrier_z + 0.13,
                0.14, 0.68, 0.06, M['dark_steel']), col)
    collect(box('Carrier_Clamp_B', carrier_x, 0, carrier_z - 0.13,
                0.14, 0.68, 0.06, M['dark_steel']), col)

    # Два троса бриделя
    rope_len = top_z - carrier_z
    for y_off in (0.22, -0.22):
        collect(cyl(f'Bridle_{y_off:+.2f}',
                    carrier_x, y_off, (top_z + carrier_z) / 2,
                    0.018, rope_len, (0, 0, 0), M['dark_steel']), col)

    # Полированная штанга — от хомута до сальниковой камеры устья
    polrod_top = carrier_z - 0.13
    polrod_bot = BASE_H + 1.20         # высота сальниковой камеры
    polrod_len = polrod_top - polrod_bot
    polrod_cz  = (polrod_top + polrod_bot) / 2
    collect(cyl('PolishedRod',
                carrier_x, 0, polrod_cz,
                0.032, polrod_len, (0, 0, 0), M['steel'], verts=16), col)

    print(f"[bridle] Готово. Хомут z={carrier_z:.2f}, штанга L={polrod_len:.2f} м")


# ============================================================
# 6. РЕДУКТОР (gearbox / speed reducer)
# ============================================================

def build_gearbox(col, M):
    """Корпус редуктора с крышкой, маслозаливной горловиной и валами."""
    print("[gearbox] Строю редуктор...")

    # Основной корпус
    collect(box('GB_Body', GB_X, 0, GB_Z,
                GB_W, GB_D, GB_H, M['dark_steel']), col)

    # Крышка
    collect(box('GB_Cover', GB_X, 0, GB_Z + GB_H / 2 + 0.05,
                GB_W - 0.12, GB_D - 0.12, 0.09, M['dark_steel']), col)

    # Маслозаливная горловина
    collect(cyl('GB_OilFill', GB_X + 0.22, 0, GB_Z + GB_H / 2 + 0.12,
                0.055, 0.18, (0, 0, 0), M['steel']), col)
    collect(cyl('GB_OilCap',  GB_X + 0.22, 0, GB_Z + GB_H / 2 + 0.22,
                0.065, 0.05, (0, 0, 0), M['dark_steel']), col)

    # Смотровое стекло (уровень масла)
    collect(box('GB_SightGlass', GB_X, GB_D / 2 + 0.03, GB_Z,
                0.10, 0.04, 0.28, M['steel']), col)

    # Выходной вал (ось кривошипа)
    collect(cyl('GB_OutShaft', GB_X, 0, CRANK_Z,
                0.075, GB_D + 0.65,
                (math.pi / 2, 0, 0), M['steel']), col)

    # Входной вал (под клиноремённый шкив)
    collect(cyl('GB_InShaft', GB_X + GB_W / 2 + 0.12, 0, GB_Z + 0.12,
                0.042, 0.32,
                (0, math.pi / 2, 0), M['steel']), col)

    # Болты крышки (упрощённо)
    for bx_off, by_off in (
        ( GB_W / 2 - 0.10,  GB_D / 2 - 0.10),
        (-GB_W / 2 + 0.10,  GB_D / 2 - 0.10),
        ( GB_W / 2 - 0.10, -GB_D / 2 + 0.10),
        (-GB_W / 2 + 0.10, -GB_D / 2 + 0.10),
    ):
        collect(cyl(f'GB_Bolt_{bx_off:.2f}_{by_off:.2f}',
                    GB_X + bx_off, by_off, GB_Z + GB_H / 2 + 0.01,
                    0.025, 0.12, (0, 0, 0), M['steel'], verts=8), col)

    print("[gearbox] Редуктор готов.")


# ============================================================
# 7. КРИВОШИПЫ + ПРОТИВОВЕСЫ (cranks / counterweights)
# ============================================================

def build_cranks(col, M):
    """
    Два кривошипа (по бокам редуктора) с противовесами.
    Кривошипный палец соединяет шатуны.
    """
    print("[cranks] Строю кривошипы...")

    for tag, y_c in (('L', GB_D / 2 + 0.12), ('R', -(GB_D / 2 + 0.12))):
        # Диск кривошипа
        collect(cyl(f'Crank_Disc_{tag}', GB_X, y_c, CRANK_Z,
                    CRANK_R + 0.09, 0.13,
                    (math.pi / 2, 0, 0), M['dark_steel'], verts=36), col)

        # Рукоять кривошипа (от центра до пальца)
        arm_len = CRANK_R
        ax = CRANK_PIN_X
        az = CRANK_PIN_Z
        bpy.ops.mesh.primitive_cube_add(location=((GB_X + ax) / 2, y_c, (CRANK_Z + az) / 2))
        arm = bpy.context.active_object
        arm.name = f'Crank_Arm_{tag}'
        arm.scale = (0.20 / 2, 0.11 / 2, arm_len / 2)
        bpy.ops.object.transform_apply(scale=True)
        arm.rotation_euler = (0, math.atan2(ax - GB_X, az - CRANK_Z), 0)
        bpy.ops.object.transform_apply(rotation=True)
        set_mat(arm, M['dark_steel'])
        collect(arm, col)

        # Кривошипный палец
        collect(cyl(f'Crank_Pin_{tag}', CRANK_PIN_X, y_c, CRANK_PIN_Z,
                    0.068, 0.38,
                    (math.pi / 2, 0, 0), M['steel']), col)

        # Противовес (на стороне, противоположной пальцу)
        cw_ang = CRANK_ANG + math.pi
        cw_r   = CRANK_R * 0.58
        cw_x = GB_X + cw_r * math.sin(cw_ang)
        cw_z = CRANK_Z + cw_r * math.cos(cw_ang)

        bpy.ops.mesh.primitive_cube_add(location=(cw_x, y_c, cw_z))
        cw = bpy.context.active_object
        cw.name = f'Counterweight_{tag}'
        cw.scale = (0.55 / 2, 0.16 / 2, 0.42 / 2)
        bpy.ops.object.transform_apply(scale=True)
        cw.rotation_euler = (0, cw_ang, 0)
        bpy.ops.object.transform_apply(rotation=True)
        set_mat(cw, M['dark_steel'])
        collect(cw, col)

    # Ось, связывающая оба кривошипных пальца
    collect(cyl('CrankPin_Shaft', CRANK_PIN_X, 0, CRANK_PIN_Z,
                0.050, GB_D + 0.35,
                (math.pi / 2, 0, 0), M['steel']), col)

    print("[cranks] Кривошипы готовы.")


# ============================================================
# 8. ШАТУНЫ + ТРАВЕРСА (pitman arms + equalizer bar)
# ============================================================

def build_pitmans(col, M):
    """Два шатуна соединяют кривошипные пальцы с траверсой балансирной балки."""
    print("[pitmans] Строю шатуны...")

    # Траверса (equalizer bar) — горизонтальная ось на хвосте балки
    collect(cyl('Equalizer_Bar', EQ_X, 0, EQ_Z,
                0.072, BEAM_Y * 2 + 1.05,
                (math.pi / 2, 0, 0), M['steel']), col)
    # Корпус подшипника траверсы (висит под балкой)
    eq_yoke_h = (PIVOT_Z - BEAM_H / 2 - FLANGE_T) - EQ_Z + 0.08
    eq_yoke_cz = EQ_Z + (PIVOT_Z - BEAM_H / 2 - FLANGE_T - EQ_Z) / 2
    collect(box('Equalizer_Yoke', EQ_X, 0, eq_yoke_cz,
                0.18, BEAM_Y * 2 - 0.05, eq_yoke_h, M['dark_steel']), col)
    # Серьги-подвески (две вертикальные пластины от нижней полки до траверсы)
    hanger_z = (PIVOT_Z - BEAM_H / 2 - FLANGE_T + EQ_Z) / 2
    hanger_h = (PIVOT_Z - BEAM_H / 2 - FLANGE_T) - EQ_Z
    for tag, y in (('L', BEAM_Y), ('R', -BEAM_Y)):
        collect(box(f'Equalizer_Hanger_{tag}', EQ_X, y, hanger_z,
                    0.10, 0.06, hanger_h + 0.06, M['steel']), col)

    # Шатуны (по одному с каждой стороны)
    for tag, y_p in (('L', BEAM_Y - 0.06), ('R', -(BEAM_Y - 0.06))):
        dx = EQ_X - CRANK_PIN_X
        dz = EQ_Z - CRANK_PIN_Z
        pit_len = math.sqrt(dx * dx + dz * dz)
        cx  = (EQ_X + CRANK_PIN_X) / 2
        cz  = (EQ_Z + CRANK_PIN_Z) / 2
        ang = math.atan2(dx, dz)

        bpy.ops.mesh.primitive_cube_add(location=(cx, y_p, cz))
        pit = bpy.context.active_object
        pit.name = f'Pitman_{tag}'
        pit.scale = (0.10 / 2, 0.085 / 2, pit_len / 2)
        bpy.ops.object.transform_apply(scale=True)
        pit.rotation_euler = (0, ang, 0)
        bpy.ops.object.transform_apply(rotation=True)
        set_mat(pit, M['steel'])
        collect(pit, col)

        # Верхний подшипниковый узел шатуна
        collect(cyl(f'Pitman_BrgTop_{tag}', EQ_X, y_p, EQ_Z,
                    0.065, 0.18,
                    (math.pi / 2, 0, 0), M['dark_steel']), col)
        # Нижний подшипниковый узел шатуна
        collect(cyl(f'Pitman_BrgBot_{tag}', CRANK_PIN_X, y_p, CRANK_PIN_Z,
                    0.065, 0.18,
                    (math.pi / 2, 0, 0), M['dark_steel']), col)

    print("[pitmans] Шатуны готовы.")


# ============================================================
# 9. ЭЛЕКТРОДВИГАТЕЛЬ + КЛИНОРЕМЁННАЯ ПЕРЕДАЧА
# ============================================================

def build_motor(col, M):
    """NEMA-frame асинхронный электродвигатель + шкивы + ремень."""
    print("[motor] Строю электродвигатель...")

    # Корпус двигателя (цилиндрический)
    collect(cyl('Motor_Body', MOTOR_X, 0, MOTOR_Z,
                0.225, 0.98, (0, math.pi / 2, 0), M['dark_steel'], verts=24), col)

    # Торцевые щиты
    collect(cyl('Motor_EndDE',  MOTOR_X - 0.55, 0, MOTOR_Z,
                0.205, 0.09, (0, math.pi / 2, 0), M['steel']), col)
    collect(cyl('Motor_EndNDE', MOTOR_X + 0.50, 0, MOTOR_Z,
                0.205, 0.09, (0, math.pi / 2, 0), M['steel']), col)

    # Рёбра охлаждения (8 продольных рёбер)
    for i in range(8):
        ang = i * math.pi / 4
        ry  =  0.245 * math.cos(ang)
        rz  = MOTOR_Z + 0.245 * math.sin(ang)
        collect(box(f'Motor_Fin_{i}', MOTOR_X, ry, rz,
                    0.88, 0.022, 0.022, M['dark_steel']), col)

    # Выходной вал
    collect(cyl('Motor_Shaft', MOTOR_X - 0.65, 0, MOTOR_Z,
                0.036, 0.24, (0, math.pi / 2, 0), M['steel']), col)

    # Монтажная рама двигателя
    collect(box('Motor_Base',   MOTOR_X, 0, MOTOR_Z - 0.28, 1.05, 0.52, 0.07, M['dark_steel']), col)
    collect(box('Motor_Rail_L', MOTOR_X, 0.22, MOTOR_Z - 0.31, 1.15, 0.09, 0.09, M['dark_steel']), col)
    collect(box('Motor_Rail_R', MOTOR_X, -0.22, MOTOR_Z - 0.31, 1.15, 0.09, 0.09, M['dark_steel']), col)

    # Клеммная коробка (junction box)
    collect(box('JBox',      MOTOR_X + 0.52, 0.34, MOTOR_Z + 0.08, 0.22, 0.17, 0.26, M['dark_steel']), col)
    collect(box('JBox_Door', MOTOR_X + 0.52, 0.42, MOTOR_Z + 0.08, 0.20, 0.02, 0.23, M['paint_gray']), col)
    collect(cyl('Conduit_1', MOTOR_X + 0.52, 0.34, MOTOR_Z - 0.22, 0.026, 0.52, (0, 0, 0), M['dark_steel']), col)

    # === Клиноремённая передача ===
    # Шкив на валу двигателя (малый)
    pulley_motor_x = MOTOR_X - 0.65
    pulley_gb_x    = GB_X + GB_W / 2 + 0.14
    pulley_gb_z    = GB_Z + 0.12

    collect(cyl('Pulley_Motor', pulley_motor_x, 0, MOTOR_Z,
                0.115, 0.15, (0, math.pi / 2, 0), M['dark_steel'], verts=24), col)

    # Шкив на валу редуктора (большой — понижение оборотов)
    collect(cyl('Pulley_GBox', pulley_gb_x, 0, pulley_gb_z,
                0.285, 0.15, (0, math.pi / 2, 0), M['dark_steel'], verts=24), col)

    # Кожух ремённой передачи (листовой металл)
    belt_cx = (pulley_motor_x + pulley_gb_x) / 2
    belt_cz = (MOTOR_Z + pulley_gb_z) / 2
    belt_lx = abs(pulley_motor_x - pulley_gb_x) + 0.40
    belt_lz = abs(MOTOR_Z - pulley_gb_z) + 0.55
    collect(box('BeltGuard', belt_cx, 0, belt_cz,
                belt_lx, 0.42, belt_lz, M['yellow']), col)

    print("[motor] Электродвигатель готов.")


# ============================================================
# 10. УСТЬЕВОЕ ОБОРУДОВАНИЕ (wellhead / christmas tree)
# ============================================================

def build_wellhead(col, M):
    """Упрощённая «ёлка» над устьем скважины."""
    print("[wellhead] Строю устьевое оборудование...")

    wz = BASE_H   # Z основания устья

    # Обсадная колонна (conductor casing)
    collect(cyl('WH_Conductor', WH_X, 0, wz + 0.22,
                0.215, 0.44 + wz * 2, (0, 0, 0), M['steel'], verts=20), col)

    # Колонная головка (нижний фланец)
    collect(cyl('WH_CasingHead',   WH_X, 0, wz + 0.32,
                0.290, 0.06, (0, 0, 0), M['steel']), col)

    # Трубная головка (tubing head)
    collect(cyl('WH_TubingHead',   WH_X, 0, wz + 0.58,
                0.230, 0.42, (0, 0, 0), M['steel']), col)
    collect(cyl('WH_TubingFlange', WH_X, 0, wz + 0.80,
                0.295, 0.06, (0, 0, 0), M['steel']), col)

    # Сальниковая камера (stuffing box)
    collect(cyl('WH_StuffBox', WH_X, 0, wz + 1.02,
                0.095, 0.38, (0, 0, 0), M['dark_steel']), col)

    # Крестовина (flow cross / tee)
    collect(cyl('WH_Tee_V', WH_X, 0, wz + 1.14, 0.065, 0.32, (0, 0, 0),            M['steel']), col)
    collect(cyl('WH_Tee_H', WH_X, 0, wz + 1.14, 0.065, 0.75, (math.pi / 2, 0, 0), M['steel']), col)

    # Арматурный вентиль (задвижка)
    collect(box('WH_Valve_Body',   WH_X, 0.40, wz + 1.14, 0.14, 0.18, 0.18, M['dark_steel']), col)
    collect(cyl('WH_Valve_Stem',   WH_X, 0.40, wz + 1.30, 0.022, 0.24, (0, 0, 0), M['steel']), col)
    collect(box('WH_Valve_Wheel',  WH_X, 0.40, wz + 1.44, 0.22, 0.04, 0.04, M['steel']), col)
    collect(box('WH_Valve_Wheel2', WH_X, 0.40, wz + 1.44, 0.04, 0.22, 0.04, M['steel']), col)

    # Выкидная линия (flow line)
    collect(cyl('WH_FlowLine_1', WH_X, 0.38, wz + 1.14,
                0.062, 1.20, (0, math.pi / 2, 0), M['steel']), col)
    collect(cyl('WH_FlowLine_2', WH_X - 0.62, 0.38, wz + 0.80,
                0.062, 0.70, (0, 0, 0), M['steel']), col)

    # Манометр
    collect(cyl('WH_Gauge', WH_X, -0.40, wz + 1.22,
                0.055, 0.28, (math.pi / 2, 0, 0), M['steel']), col)
    collect(cyl('WH_Gauge_Face', WH_X, -0.55, wz + 1.22,
                0.052, 0.04, (math.pi / 2, 0, 0), M['paint_gray']), col)

    print("[wellhead] Устьевое оборудование готово.")


# ============================================================
# 11. ОГРАЖДЕНИЯ, ПЛАТФОРМА, ЛЕСТНИЦА, ПОРУЧНИ
# ============================================================

def build_safety(col, M):
    """Кожух кривошипа, рабочая площадка, лестница, поручни."""
    print("[safety] Строю ограждения и платформу...")

    # --- Кожух кривошипа (листовые стенки по бокам от кривошипов) ---
    cg_y = GB_D / 2 + 0.20
    cg_h = CRANK_R * 2 + 0.30
    for tag, y_s in (('L', cg_y), ('R', -cg_y)):
        collect(box(f'CrankGuard_{tag}', GB_X, y_s, CRANK_Z,
                    CRANK_R * 2 + 0.40, 0.04, cg_h, M['yellow']), col)
    # Верхняя крышка кожуха
    collect(box('CrankGuard_Top', GB_X, 0, CRANK_Z + CRANK_R + 0.16,
                CRANK_R * 2 + 0.38, cg_y * 2, 0.04, M['yellow']), col)

    # --- Рабочая площадка (рядом с двигателем, не над кривошипами) ---
    # Платформа смещена в сторону двигателя; кривошипы вращаются под открытым небом
    platform_z = max(CRANK_Z + CRANK_R + 0.20, GB_Z + GB_H / 2 + 0.20)
    plat_cx = (GB_X + GB_W / 2 + MOTOR_X - 0.65) / 2  # между редуктором и двигателем
    plat_lx = MOTOR_X - 0.65 - (GB_X + GB_W / 2) + 0.10
    collect(box('Platform', plat_cx, 0, platform_z,
                plat_lx, BASE_W + 0.25, 0.06, M['dark_steel']), col)

    # Решётка площадки (имитация полосами)
    n_grate = max(3, int(plat_lx / 0.30))
    for i in range(n_grate):
        xp = plat_cx - plat_lx / 2 + (i + 0.5) * plat_lx / n_grate
        collect(box(f'Grating_{i}', xp, 0, platform_z + 0.02,
                    0.03, BASE_W + 0.22, 0.03, M['dark_steel']), col)

    # --- Стойки поручней ---
    rail_z = platform_z + 0.55
    rail_h = 1.10
    n_posts = max(3, int(plat_lx / 0.80))
    for pi in range(n_posts):
        xp = plat_cx - plat_lx / 2 + (pi + 0.5) * plat_lx / n_posts
        for tag, y_r in (('L', BASE_W / 2 + 0.12), ('R', -(BASE_W / 2 + 0.12))):
            collect(cyl(f'RailPost_{pi}_{tag}', xp, y_r, rail_z,
                        0.026, rail_h, (0, 0, 0), M['yellow']), col)

    # --- Верхний и средний поручни ---
    for dz, sfx in ((rail_h * 0.95, 'Top'), (rail_h * 0.50, 'Mid')):
        for tag, y_r in (('L', BASE_W / 2 + 0.12), ('R', -(BASE_W / 2 + 0.12))):
            collect(box(f'Rail_{sfx}_{tag}', plat_cx, y_r, platform_z + dz,
                        plat_lx, 0.04, 0.04, M['yellow']), col)

    # --- Лестница доступа на площадку ---
    lad_x = plat_cx - plat_lx / 2 + 0.20
    lad_y = BASE_W / 2 + 0.14
    num_rungs = 7
    for tag, y_s in (('Str_L', lad_y), ('Str_R', lad_y + 0.18)):
        collect(box(f'Ladder_{tag}', lad_x, y_s, platform_z / 2,
                    0.04, 0.04, platform_z + 0.10, M['yellow']), col)
    for i in range(num_rungs):
        rz = 0.28 + i * (platform_z - 0.28) / (num_rungs - 1)
        collect(box(f'Ladder_Rung_{i}', lad_x, lad_y + 0.09, rz,
                    0.04, 0.22, 0.025, M['yellow']), col)

    # --- Табличка (nameplate) ---
    collect(box('Nameplate', GB_X, GB_D / 2 + 0.04, GB_Z + 0.22,
                0.32, 0.02, 0.16, M['yellow']), col)

    print("[safety] Ограждения и платформа готовы.")


# ============================================================
# 12. ОСВЕЩЕНИЕ, КАМЕРА, НАСТРОЙКИ СЦЕНЫ
# ============================================================

def build_scene():
    """Солнечный свет, заполняющий свет, камера и настройки рендера."""
    print("[scene] Настраиваю освещение и камеру...")

    # Солнце (ключевой свет)
    bpy.ops.object.light_add(type='SUN', location=(8, -14, 16))
    sun = bpy.context.active_object
    sun.name = 'Light_Sun'
    sun.data.energy = 4.5
    sun.data.angle  = math.radians(0.6)
    sun.rotation_euler = (math.radians(52), 0, math.radians(28))

    # Заполняющий свет (имитация неба)
    bpy.ops.object.light_add(type='AREA', location=(-10, 8, 14))
    sky = bpy.context.active_object
    sky.name = 'Light_Sky'
    sky.data.energy = 900
    sky.data.size   = 10
    sky.rotation_euler = (math.radians(58), 0, math.radians(-55))

    # Отражённый от земли свет
    bpy.ops.object.light_add(type='AREA', location=(0, 0, -0.5))
    bounce = bpy.context.active_object
    bounce.name = 'Light_Bounce'
    bounce.data.energy = 220
    bounce.data.size   = 18
    bounce.rotation_euler = (math.radians(180), 0, 0)

    # Камера
    bpy.ops.object.camera_add(location=(14, -11, 7.5))
    cam = bpy.context.active_object
    cam.name = 'Camera_Main'
    cam.rotation_euler = (math.radians(62), 0, math.radians(52))
    cam.data.lens = 35
    bpy.context.scene.camera = cam

    # Настройки рендера (Cycles)
    sc = bpy.context.scene
    sc.render.engine           = 'CYCLES'
    sc.cycles.samples          = 256
    sc.render.resolution_x     = 1920
    sc.render.resolution_y     = 1080
    sc.render.film_transparent = False

    # Небо (World background)
    world = sc.world or bpy.data.worlds.new('World')
    sc.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get('Background')
    if bg_node:
        bg_node.inputs['Color'].default_value    = (0.52, 0.63, 0.74, 1.0)
        bg_node.inputs['Strength'].default_value = 0.75

    print("[scene] Сцена настроена.")
    print("  Подсказка: NUMPAD_0 — вид из камеры | F12 — рендер")


# ============================================================
# ГЛАВНАЯ ФУНКЦИЯ
# ============================================================

def main():
    print("=" * 60)
    print("  Генерация нефтяного станка-качалки (API 114D)")
    print("=" * 60)

    clear_scene()

    # Коллекция для всех деталей станка
    col = bpy.data.collections.new('OilPumpJack')
    bpy.context.scene.collection.children.link(col)

    M = build_materials()

    build_base(col, M)
    build_sampson(col, M)
    build_beam(col, M)
    build_horsehead(col, M)
    build_bridle(col, M)
    build_gearbox(col, M)
    build_cranks(col, M)
    build_pitmans(col, M)
    build_motor(col, M)
    build_wellhead(col, M)
    build_safety(col, M)
    build_scene()

    obj_count = len(list(col.objects))
    mat_count = len(bpy.data.materials)
    print("=" * 60)
    print(f"  ГОТОВО!  Объектов: {obj_count}  |  Материалов: {mat_count}")
    print("=" * 60)


main()
