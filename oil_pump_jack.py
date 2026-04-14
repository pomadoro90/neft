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
import bmesh
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


def leg_3d(name, x1, y1, z1, x2, y2, z2, w, d, mat=None):
    """
    Прямоугольный брус от точки (x1,y1,z1) до (x2,y2,z2).
    w, d — поперечные размеры сечения.
    Использует mathutils.Quaternion для произвольной 3D-ориентации.
    """
    import mathutils
    dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    cx, cy, cz = (x1 + x2) / 2, (y1 + y2) / 2, (z1 + z2) / 2

    bpy.ops.mesh.primitive_cube_add(location=(cx, cy, cz))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (w / 2, d / 2, length / 2)
    bpy.ops.object.transform_apply(scale=True)

    direction = mathutils.Vector((dx, dy, dz)).normalized()
    rot = mathutils.Vector((0, 0, 1)).rotation_difference(direction)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rot
    bpy.ops.object.transform_apply(rotation=True)
    obj.rotation_mode = 'XYZ'

    if mat:
        set_mat(obj, mat)
    return obj


def make_half_disc(name, cx, cy, cz, radius, thickness, n_segs=40, mat=None):
    """
    Сгенерировать сплошной полудиск через bmesh.
    Профиль — полуокружность от верха (0,+R) через перёд (+R,0) к низу (0,-R),
    выдавлена по Y на thickness. Плоская задняя стенка при x=cx.
    Используется для корпуса головки балансира («horsehead»).
    """
    mesh = bpy.data.meshes.new(name + '_Mesh')
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    # 2D-профиль (полуокружность вперёд)
    profile = []
    for i in range(n_segs + 1):
        a = math.pi / 2 - i * math.pi / n_segs
        profile.append((radius * math.cos(a), radius * math.sin(a)))

    # Вершины на двух плоскостях по Y
    v_front = [bm.verts.new((cx + x, cy + thickness / 2, cz + z)) for x, z in profile]
    v_back  = [bm.verts.new((cx + x, cy - thickness / 2, cz + z)) for x, z in profile]

    # Боковая поверхность вдоль дуги (грани-четырёхугольники)
    for i in range(len(profile) - 1):
        bm.faces.new([v_front[i], v_front[i + 1], v_back[i + 1], v_back[i]])

    # Передняя и задняя плоские грани (n-gon)
    bm.faces.new(list(reversed(v_front)))
    bm.faces.new(v_back)

    # Замыкающая задняя стенка (плоский прямоугольник x = cx)
    bm.faces.new([v_front[0], v_back[0], v_back[-1], v_front[-1]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    if mat:
        set_mat(obj, mat)
    return obj


def make_pacman_disc(name, cx, cy, cz, radius, thickness,
                     bite_center_deg, bite_width_deg, n_segs=48, mat=None):
    """
    Создать диск-противовес с «выкусом» (Pac-Man формы),
    как у настоящих rotary counterweights станков-качалок.
      bite_center_deg — направление центра выкуса (от +X в плоскости XZ, против часовой)
      bite_width_deg  — угловая ширина выкуса (полная)
    Ось диска — Y.
    """
    mesh = bpy.data.meshes.new(name + '_Mesh')
    obj  = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(obj)

    bm = bmesh.new()

    bite_c = math.radians(bite_center_deg)
    bite_w = math.radians(bite_width_deg)
    arc_start = bite_c + bite_w / 2          # начало оставшейся дуги
    arc_span  = 2 * math.pi - bite_w          # длина оставшейся дуги

    # Центральные вершины (для веера)
    v_cf = bm.verts.new((cx, cy + thickness / 2, cz))
    v_cb = bm.verts.new((cx, cy - thickness / 2, cz))

    v_front, v_back = [], []
    for i in range(n_segs + 1):
        a = arc_start + i * arc_span / n_segs
        x = radius * math.cos(a)
        z = radius * math.sin(a)
        v_front.append(bm.verts.new((cx + x, cy + thickness / 2, cz + z)))
        v_back.append( bm.verts.new((cx + x, cy - thickness / 2, cz + z)))

    # Передняя грань (веер)
    for i in range(len(v_front) - 1):
        bm.faces.new([v_cf, v_front[i], v_front[i + 1]])
    # Задняя грань (веер)
    for i in range(len(v_back) - 1):
        bm.faces.new([v_cb, v_back[i + 1], v_back[i]])
    # Боковая поверхность (по дуге)
    for i in range(len(v_front) - 1):
        bm.faces.new([v_front[i], v_front[i + 1], v_back[i + 1], v_back[i]])
    # Две плоские стенки выкуса
    bm.faces.new([v_cf, v_front[0], v_back[0], v_cb])
    bm.faces.new([v_cb, v_back[-1], v_front[-1], v_cf])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    if mat:
        set_mat(obj, mat)
    return obj


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

SP_BASE_X = 1.60       # X-разнос ног вперёд/назад от шарнира (A-форма видна сбоку)
SP_BASE_Y = 1.00       # Y-полуширина основания стойки Сэмпсона
SP_LEG_W  = 0.18       # ширина сечения ноги (I-профиль)
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

EQ_X = PIVOT_X - BEAM_REAR + 0.38   # X траверсы (equalizer) — ближе к заднему концу балки
# Траверса висит чуть ниже нижней полки балки, чтобы шатуны не пересекали балку
EQ_Z = PIVOT_Z - BEAM_H / 2 - FLANGE_T - 0.08

MOTOR_X = GB_X + 1.50   # X центра электродвигателя (ближе к редуктору)
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
    M['navy'] = new_mat('M_PaintGray',  (0.38, 0.40, 0.42), metallic=0.05, roughness=0.55)
    M['paint_red']  = new_mat('M_PaintRed',   (0.62, 0.07, 0.07), metallic=0.05, roughness=0.50)
    M['yellow']     = new_mat('M_Yellow',     (0.90, 0.76, 0.02), metallic=0.05, roughness=0.50)
    M['orange']     = new_mat('M_Orange',     (0.95, 0.42, 0.05), metallic=0.10, roughness=0.45)
    M['navy']       = new_mat('M_Navy',       (0.12, 0.16, 0.22), metallic=0.15, roughness=0.45)
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
    """
    A-образная рама (Sampson post): четыре ноги расходятся от вершины
    (оси шарнира) к четырём угловым точкам опоры на раме-салазках.
    В боковой проекции образует отчётливую А-форму — ключевой
    визуальный признак станка-качалки.
    """
    print("[sampson] Строю стойку Сэмпсона (4-ноги, A-форма)...")

    z_bot = BASE_H    # 0.18 m — основание
    z_top = PIVOT_Z   # 4.20 m — ось шарнира

    # ---- 4 угловых ноги ----------------------------------------
    # Координаты опорных пяток (все ноги сходятся к PIVOT_X, 0, z_top)
    feet = [
        ('FL', PIVOT_X + SP_BASE_X,  SP_BASE_Y),   # перед-лево
        ('FR', PIVOT_X + SP_BASE_X, -SP_BASE_Y),   # перед-право
        ('RL', PIVOT_X - SP_BASE_X,  SP_BASE_Y),   # зад-лево
        ('RR', PIVOT_X - SP_BASE_X, -SP_BASE_Y),   # зад-право
    ]
    for tag, xb, yb in feet:
        obj = leg_3d(f'SP_Leg_{tag}',
                     PIVOT_X, 0, z_top,
                     xb, yb, z_bot,
                     SP_LEG_W, SP_LEG_D, M['navy'])
        collect(obj, col)

    # ---- Горизонтальные поперечины (Y-направление) на трёх уровнях ----
    # Соединяют FL-FR (передняя пара) и RL-RR (задняя пара).
    for frac in (0.28, 0.54, 0.80):
        z_h = z_bot + (z_top - z_bot) * frac
        f   = frac                              # от основания (1) к вершине (0)
        y_h = SP_BASE_Y * (1.0 - frac)
        x_f = PIVOT_X + SP_BASE_X * (1.0 - frac)   # передняя пара
        x_r = PIVOT_X - SP_BASE_X * (1.0 - frac)   # задняя пара
        collect(box(f'SP_FBrace_{frac:.2f}', x_f, 0, z_h,
                    SP_LEG_D, y_h * 2 + SP_LEG_W, 0.13, M['navy']), col)
        collect(box(f'SP_RBrace_{frac:.2f}', x_r, 0, z_h,
                    SP_LEG_D, y_h * 2 + SP_LEG_W, 0.13, M['navy']), col)

    # ---- Боковые горизонтальные связи (X-направление) — «ступени» ----
    # Соединяют FL-RL (левая пара) и FR-RR (правая пара).
    # В боковой проекции выглядят как перекладины A-рамы.
    for frac in (0.28, 0.54, 0.80):
        z_h = z_bot + (z_top - z_bot) * frac
        x_f = PIVOT_X + SP_BASE_X * (1.0 - frac)
        x_r = PIVOT_X - SP_BASE_X * (1.0 - frac)
        lx  = x_f - x_r + SP_LEG_D
        for y_s, ytag in ((SP_BASE_Y * (1.0 - frac), 'L'),
                          (-SP_BASE_Y * (1.0 - frac), 'R')):
            collect(box(f'SP_SBrace_{ytag}_{frac:.2f}',
                        (x_f + x_r) / 2, y_s, z_h,
                        lx, SP_LEG_D, 0.10, M['steel']), col)

    # ---- X-образные диагональные раскосы (по каждой Y-стороне) ----
    # Перекрёстная связь между передней и задней ногой одного Y-борта.
    for y_sign, ytag in ((1, 'L'), (-1, 'R')):
        yb = y_sign * SP_BASE_Y
        # нижняя треть крест
        obj = leg_3d(f'SP_XBrace_{ytag}_1',
                     PIVOT_X + SP_BASE_X, yb, z_bot,
                     PIVOT_X,             yb, z_bot + (z_top - z_bot) * 0.54,
                     0.09, 0.07, M['steel'])
        collect(obj, col)
        obj = leg_3d(f'SP_XBrace_{ytag}_2',
                     PIVOT_X - SP_BASE_X, yb, z_bot,
                     PIVOT_X,             yb, z_bot + (z_top - z_bot) * 0.54,
                     0.09, 0.07, M['steel'])
        collect(obj, col)

    # ---- Лестница (на переднем фасаде, по левой стороне) ----
    n_rungs = 8
    lad_x_bot = PIVOT_X + SP_BASE_X * 0.68
    lad_x_top = PIVOT_X + SP_BASE_X * 0.08
    lad_y     = SP_BASE_Y * 0.58
    # Тетивы
    for y_s, ltag in ((lad_y, 'L'), (-lad_y, 'R')):
        obj = leg_3d(f'SP_LadStr_{ltag}',
                     lad_x_bot, y_s, z_bot,
                     lad_x_top, y_s, z_top * 0.94,
                     0.040, 0.040, M['dark_steel'])
        collect(obj, col)
    # Перекладины
    for i in range(n_rungs):
        t = (i + 0.5) / n_rungs
        rx = lad_x_bot + (lad_x_top - lad_x_bot) * t
        rz = z_bot      + (z_top * 0.94 - z_bot) * t
        collect(box(f'SP_LadRung_{i}', rx, 0, rz,
                    0.035, lad_y * 2, 0.025, M['dark_steel']), col)

    # ---- Корпус подшипника шарнира (компактный, по центру рамы) ----
    collect(box('SP_BrgHousing', PIVOT_X, 0, PIVOT_Z,
                0.40, 0.40, 0.38, M['dark_steel']), col)
    collect(box('SP_BrgCap', PIVOT_X, 0, PIVOT_Z + 0.21,
                0.34, 0.36, 0.12, M['dark_steel']), col)

    # Опорный вал шарнира
    collect(cyl('SP_PivotShaft', PIVOT_X, 0, PIVOT_Z,
                0.072, BEAM_Y * 2 + 0.85,
                (math.pi / 2, 0, 0), M['steel']), col)

    print("[sampson] Стойка готова (4-ноги, A-форма).")


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
                    total, BEAM_WEB_W, BEAM_H, M['navy']), col)
        # Верхняя полка
        collect(box(f'Beam_TFlg_{tag}',   cx, y, PIVOT_Z + BEAM_H / 2,
                    total, FLANGE_W, FLANGE_T, M['navy']), col)
        # Нижняя полка
        collect(box(f'Beam_BFlg_{tag}',   cx, y, PIVOT_Z - BEAM_H / 2,
                    total, FLANGE_W, FLANGE_T, M['navy']), col)

    # Поперечные диафрагмы через каждый ~1 м
    for i, xp in enumerate([
        PIVOT_X,
        PIVOT_X + 1.0, PIVOT_X + 2.2,
        PIVOT_X - 1.0, PIVOT_X - 2.2, PIVOT_X - 3.4,
    ]):
        collect(box(f'Beam_Diaphragm_{i}', xp, 0, PIVOT_Z,
                    0.06, BEAM_Y * 2, BEAM_H + 0.04, M['steel']), col)

    # Торцевые заглушки балки (видны как тёмные пластины на концах)
    for tag, xe in (('Front', PIVOT_X + BEAM_FRONT - 0.04),
                    ('Rear',  PIVOT_X - BEAM_REAR  + 0.04)):
        collect(box(f'Beam_EndPlate_{tag}', xe, 0, PIVOT_Z,
                    0.08, BEAM_Y * 2 + 0.22, BEAM_H + 0.10, M['steel']), col)

    # Хвостовой противовес (tail weight) — чугунный блок на заднем конце балки
    # Балансирует нагрузку от головки и полированной штанги
    tail_x = PIVOT_X - BEAM_REAR + 0.24
    collect(box('Beam_TailWeight', tail_x, 0, PIVOT_Z,
                0.42, BEAM_Y * 2 + 0.24, 0.58, M['dark_steel']), col)
    # Крепёжная планка хвостового противовеса
    collect(box('Beam_TailWeight_Plate', tail_x, 0, PIVOT_Z + 0.32,
                0.46, BEAM_Y * 2 + 0.30, 0.06, M['steel']), col)

    print("[beam] Балка готова.")


# ============================================================
# 4. ГОЛОВКА (horsehead)
# ============================================================

def build_horsehead(col, M):
    """
    Головка балансира («horsehead») — сплошной оранжевый полудиск
    на конце балки, как на референсе.
       Центр дуги: (HH_TIP_X, 0, PIVOT_Z)
       Радиус:     HH_R
       Толщина:    BEAM_Y * 2 + 0.10 (немного шире, чем балка)
    """
    print("[horsehead] Строю головку (solid bmesh)...")

    arc_cx = HH_TIP_X
    arc_cz = PIVOT_Z
    hh_thick = BEAM_Y * 2 + 0.10

    # === Монтажная плита крепления головки к торцу балки ===
    # Тёмная стальная пластина на плоской задней грани полудиска —
    # имитирует болтовой фланец, которым головка крепится к двутавру балки.
    collect(box('HH_MountPlate', arc_cx - 0.055, 0, arc_cz,
                0.11, hh_thick + 0.04, BEAM_H + 0.14, M['dark_steel']), col)
    # Верхний усиливающий ребро-воротник
    collect(box('HH_MountRib', arc_cx - 0.04, 0, arc_cz + BEAM_H / 2 + 0.08,
                0.08, hh_thick + 0.08, 0.08, M['dark_steel']), col)

    # === Оранжевый сплошной корпус головки (mesh) ===
    head = make_half_disc('HorseHead_Body',
                          arc_cx, 0, arc_cz,
                          HH_R, hh_thick,
                          n_segs=40, mat=M['orange'])
    collect(head, col)

    # === Шкив (sheave) в нижней точке дуги — где трос выходит вертикально ===
    sheave_x = arc_cx
    sheave_z = arc_cz - HH_R
    collect(cyl('HH_Sheave', sheave_x, 0, sheave_z,
                0.10, hh_thick + 0.10,
                (math.pi / 2, 0, 0), M['dark_steel'], verts=24), col)

    # === Узел подвеса бриделя — серьга под шкивом ===
    collect(box('HH_BridleEar', sheave_x, 0, sheave_z - 0.10,
                0.12, 0.30, 0.10, M['dark_steel']), col)

    # Сохраняем глобальную точку подвеса
    global BRIDLE_TOP_X, BRIDLE_TOP_Z
    BRIDLE_TOP_X = sheave_x
    BRIDLE_TOP_Z = sheave_z - 0.10

    print(f"[horsehead] Готово. Полудиск R={HH_R:.2f}, толщина={hh_thick:.2f}")
    print(f"[horsehead] Точка подвеса: x={BRIDLE_TOP_X:.2f}, z={BRIDLE_TOP_Z:.2f}")


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

    # === Монтажный постамент редуктора (соединяет редуктор с рамой-основанием) ===
    # Редуктор висит: GB_Z - GB_H/2 = 0.475m, рама = BASE_H = 0.18m → зазор 0.295m.
    ped_h = GB_Z - GB_H / 2 - BASE_H   # = 0.295 m
    ped_cz = BASE_H + ped_h / 2         # = 0.3275 m
    # Четыре угловые стойки постамента
    for i, (lx, ly) in enumerate((
        ( GB_W / 2 - 0.13,  GB_D / 2 - 0.13),
        (-GB_W / 2 + 0.13,  GB_D / 2 - 0.13),
        ( GB_W / 2 - 0.13, -(GB_D / 2 - 0.13)),
        (-GB_W / 2 + 0.13, -(GB_D / 2 - 0.13)),
    )):
        collect(box(f'GB_Ped_{i}', GB_X + lx, ly, ped_cz,
                    0.13, 0.13, ped_h, M['dark_steel']), col)
    # Две продольные балки у основания постамента (видны под редуктором)
    for ly in (GB_D / 2 - 0.13, -(GB_D / 2 - 0.13)):
        collect(box(f'GB_PedBeam_{ly:.2f}', GB_X, ly, BASE_H + 0.06,
                    GB_W - 0.22, 0.15, 0.12, M['dark_steel']), col)

    print("[gearbox] Редуктор готов.")


# ============================================================
# 7. КРИВОШИПЫ + ПРОТИВОВЕСЫ (cranks / counterweights)
# ============================================================

def build_cranks(col, M):
    """
    Кривошипная группа: два больших ОРАНЖЕВЫХ Pac-Man-диска (rotary counterweight)
    по бокам редуктора. Каждый диск имеет «выкус» в направлении кривошипного пальца —
    основная масса противовеса распределена на противоположной стороне.

    Оранжевый цвет соответствует канону раскраски станков-качалок (как на референсе).
    """
    print("[cranks] Строю Pac-Man противовесы...")

    # Радиус большого диска-противовеса (≈ 1.4× радиуса кривошипа)
    DISC_R     = CRANK_R + 0.30
    DISC_THICK = 0.18

    # Угол кривошипного пальца в математической системе (от +X, против часовой)
    pin_math_deg = math.degrees(math.pi / 2 - CRANK_ANG)   # 90° - CRANK_ANG
    # Выкус: сектор, направленный от центра в сторону пальца
    BITE_W = 100.0   # градусов — ширина выкуса (вырезанный сектор)

    # Две стороны редуктора
    for tag, y_c in (('L', GB_D / 2 + 0.13), ('R', -(GB_D / 2 + 0.13))):
        # Большой Pac-Man диск-противовес
        disc = make_pacman_disc(
            f'Counterweight_{tag}',
            GB_X, y_c, CRANK_Z,
            DISC_R, DISC_THICK,
            bite_center_deg=pin_math_deg,
            bite_width_deg=BITE_W,
            n_segs=64,
            mat=M['orange'],
        )
        collect(disc, col)

        # Центральная ступица (тёмная)
        collect(cyl(f'Crank_Hub_{tag}', GB_X, y_c, CRANK_Z,
                    0.18, DISC_THICK + 0.06,
                    (math.pi / 2, 0, 0), M['dark_steel'], verts=24), col)

        # Кривошипный палец — выходит наружу (в сторону шатуна)
        pin_y_outer = y_c + DISC_THICK / 2 + 0.18
        pin_y_inner = y_c - 0.04
        pin_len = pin_y_outer - pin_y_inner
        pin_y_c = (pin_y_outer + pin_y_inner) / 2
        collect(cyl(f'Crank_Pin_{tag}', CRANK_PIN_X, pin_y_c, CRANK_PIN_Z,
                    0.068, pin_len,
                    (math.pi / 2, 0, 0), M['steel']), col)

        # Гайка-фиксатор пальца снаружи
        collect(cyl(f'Crank_PinNut_{tag}', CRANK_PIN_X, pin_y_outer + 0.02, CRANK_PIN_Z,
                    0.085, 0.05,
                    (math.pi / 2, 0, 0), M['dark_steel'], verts=8), col)

        # Усиливающее ребро на диске (от ступицы к пальцу — «лучик» бочонка)
        rib_cx = (GB_X + CRANK_PIN_X) / 2
        rib_cz = (CRANK_Z + CRANK_PIN_Z) / 2
        rib_len = CRANK_R
        rib_ang = math.atan2(CRANK_PIN_X - GB_X, CRANK_PIN_Z - CRANK_Z)
        bpy.ops.mesh.primitive_cube_add(location=(rib_cx, y_c + DISC_THICK / 2 + 0.02, rib_cz))
        rib = bpy.context.active_object
        rib.name = f'Crank_Rib_{tag}'
        rib.scale = (0.10 / 2, 0.04 / 2, rib_len / 2)
        bpy.ops.object.transform_apply(scale=True)
        rib.rotation_euler = (0, rib_ang, 0)
        bpy.ops.object.transform_apply(rotation=True)
        set_mat(rib, M['dark_steel'])
        collect(rib, col)

    # Сквозная ось через оба диска (внутри редуктора)
    collect(cyl('Crank_Shaft', GB_X, 0, CRANK_Z,
                0.075, GB_D + 0.50,
                (math.pi / 2, 0, 0), M['steel']), col)

    print(f"[cranks] Готово. R(диска)={DISC_R:.2f}, выкус={BITE_W:.0f}°")


# ============================================================
# 8. ШАТУНЫ + ТРАВЕРСА (pitman arms + equalizer bar)
# ============================================================

def build_pitmans(col, M):
    """Два шатуна соединяют кривошипные пальцы с траверсой балансирной балки."""
    print("[pitmans] Строю шатуны...")

    # Траверса (equalizer bar) — горизонтальная ось от шатуна до шатуна
    DISC_THICK = 0.18
    pitman_y_off = (GB_D / 2 + 0.13) + DISC_THICK / 2 + 0.10
    eq_bar_len = pitman_y_off * 2 + 0.30
    collect(cyl('Equalizer_Bar', EQ_X, 0, EQ_Z,
                0.072, eq_bar_len,
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

    # Шатуны идут СНАРУЖИ от дисков-противовесов (чтобы не пересекать их)
    # Y-позиция шатуна = край диска + небольшой зазор
    DISC_THICK = 0.18
    pitman_y_offset = (GB_D / 2 + 0.13) + DISC_THICK / 2 + 0.10   # = 0.85
    for tag, y_p in (('L', pitman_y_offset), ('R', -pitman_y_offset)):
        dx = EQ_X - CRANK_PIN_X
        dz = EQ_Z - CRANK_PIN_Z
        pit_len = math.sqrt(dx * dx + dz * dz)
        cx  = (EQ_X + CRANK_PIN_X) / 2
        cz  = (EQ_Z + CRANK_PIN_Z) / 2
        ang = math.atan2(dx, dz)

        bpy.ops.mesh.primitive_cube_add(location=(cx, y_p, cz))
        pit = bpy.context.active_object
        pit.name = f'Pitman_{tag}'
        pit.scale = (0.14 / 2, 0.11 / 2, pit_len / 2)   # толще для видимости
        bpy.ops.object.transform_apply(scale=True)
        pit.rotation_euler = (0, ang, 0)
        bpy.ops.object.transform_apply(rotation=True)
        set_mat(pit, M['navy'])
        collect(pit, col)

        # Верхний подшипниковый узел шатуна
        collect(cyl(f'Pitman_BrgTop_{tag}', EQ_X, y_p, EQ_Z,
                    0.090, 0.22,
                    (math.pi / 2, 0, 0), M['dark_steel']), col)
        # Нижний подшипниковый узел шатуна (на кривошипном пальце)
        collect(cyl(f'Pitman_BrgBot_{tag}', CRANK_PIN_X, y_p, CRANK_PIN_Z,
                    0.090, 0.22,
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
    collect(box('JBox_Door', MOTOR_X + 0.52, 0.42, MOTOR_Z + 0.08, 0.20, 0.02, 0.23, M['navy']), col)
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

    # Кожух ремённой передачи (трёхпанельный: две боковины + верхняя крышка)
    # Форма следует контуру ремня — трапеция в боковом виде
    belt_cx = (pulley_motor_x + pulley_gb_x) / 2
    belt_cz = (MOTOR_Z + pulley_gb_z) / 2
    belt_lx = abs(pulley_motor_x - pulley_gb_x) + 0.44
    belt_lz = abs(MOTOR_Z - pulley_gb_z) + 0.62
    bg_half_y = 0.23   # половина ширины кожуха по Y
    # Две боковые стенки
    for tag, y_bg in (('F', bg_half_y), ('B', -bg_half_y)):
        collect(box(f'BeltGuard_{tag}', belt_cx, y_bg, belt_cz,
                    belt_lx, 0.035, belt_lz, M['yellow']), col)
    # Верхняя крышка
    collect(box('BeltGuard_Top', belt_cx, 0, belt_cz + belt_lz / 2 - 0.04,
                belt_lx, bg_half_y * 2 + 0.04, 0.06, M['yellow']), col)
    # Нижняя перемычка (торец кожуха, не закрывает доступ к ремню)
    collect(box('BeltGuard_Bot', belt_cx, 0, belt_cz - belt_lz / 2 + 0.04,
                belt_lx, bg_half_y * 2 + 0.04, 0.06, M['yellow']), col)

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
                0.052, 0.04, (math.pi / 2, 0, 0), M['navy']), col)

    print("[wellhead] Устьевое оборудование готово.")


# ============================================================
# 11. ОГРАЖДЕНИЯ, ПЛАТФОРМА, ЛЕСТНИЦА, ПОРУЧНИ
# ============================================================

def build_safety(col, M):
    """
    Компактная рабочая площадка сбоку от редуктора + поручни + табличка.
    Кожух кривошипа УДАЛЁН — в реальных машинах кривошипы открыты
    (как на референсах); большие жёлтые панели искажали силуэт.
    """
    print("[safety] Строю площадку и поручни...")

    # --- Рабочая площадка сбоку от редуктора (на уровне верха корпуса) ---
    platform_z = GB_Z + GB_H / 2 + 0.10    # = 1.525 m
    plat_cx    = GB_X + GB_W / 2 + 0.55    # = -1.625 m (правее редуктора)
    plat_lx    = 1.10
    plat_ly    = BASE_W + 0.20

    collect(box('Platform', plat_cx, 0, platform_z,
                plat_lx, plat_ly, 0.06, M['dark_steel']), col)
    # Решётка площадки (3 полосы)
    for i in range(3):
        xp = plat_cx - plat_lx / 2 + (i + 0.5) * plat_lx / 3
        collect(box(f'Grating_{i}', xp, 0, platform_z + 0.02,
                    0.03, plat_ly - 0.04, 0.03, M['dark_steel']), col)

    # --- Поручни (4 стойки + два горизонтальных поручня) ---
    rail_h = 1.05
    for pi, xp in enumerate([plat_cx - plat_lx * 0.38,
                              plat_cx + plat_lx * 0.38]):
        for tag, yr in (('L', plat_ly / 2), ('R', -plat_ly / 2)):
            collect(cyl(f'RailPost_{pi}_{tag}', xp, yr,
                        platform_z + rail_h / 2,
                        0.026, rail_h, (0, 0, 0), M['yellow']), col)
    for dz, sfx in ((rail_h * 0.96, 'Top'), (rail_h * 0.52, 'Mid')):
        for tag, yr in (('L', plat_ly / 2), ('R', -plat_ly / 2)):
            collect(box(f'Rail_{sfx}_{tag}', plat_cx, yr, platform_z + dz,
                        plat_lx, 0.04, 0.04, M['yellow']), col)

    # --- Ограждение входа на платформу (два столбика + цепочка) ---
    gate_x = plat_cx - plat_lx / 2 - 0.05
    for tag, yr in (('L', plat_ly / 2), ('R', -plat_ly / 2)):
        collect(cyl(f'GatePost_{tag}', gate_x, yr, platform_z + 0.55,
                    0.022, 1.10, (0, 0, 0), M['yellow']), col)

    # --- Табличка на редукторе (nameplate) ---
    collect(box('Nameplate', GB_X, GB_D / 2 + 0.04, GB_Z + 0.22,
                0.32, 0.02, 0.16, M['yellow']), col)

    print("[safety] Площадка и поручни готовы.")


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
