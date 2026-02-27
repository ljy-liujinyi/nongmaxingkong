# app.py
# 农技百科 - 生产部署版

import os
import base64
from flask import Flask, render_template, request, jsonify
from aip import AipImageClassify
import time
import hashlib
import pickle
from PIL import Image, ImageStat, ImageEnhance, ImageFilter, ImageOps
import math
import numpy as np
from collections import Counter
import re
from knowledge_base import FOOD_KNOWLEDGE, DISEASE_KNOWLEDGE, NAME_MAPPING, DISEASE_KEYWORDS

# 抑制版本警告
import warnings
warnings.filterwarnings("ignore")

# 初始化Flask应用
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10MB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CACHE_FOLDER'] = 'cache'

# 创建必要目录
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CACHE_FOLDER'], exist_ok=True)

# ==================== 百度AI配置 ====================
APP_ID = '7467354'
API_KEY = 'NXA5N1A6J36hIDrxPVX4yBSA'
SECRET_KEY = 'YJoto1J118cPhjIEFhkUNyVNlckn578B'

try:
    client = AipImageClassify(APP_ID, API_KEY, SECRET_KEY)
    print("✅ 百度AI客户端初始化成功")
except Exception as e:
    print(f"⚠️ 百度AI客户端初始化失败: {e}")
    client = None

# ==================== 作物-病害严格关联库 ====================
# 每种作物只能有特定的病害，禁止跨作物匹配
CROP_DISEASE_STRICT = {
    # 粮食作物
    "水稻": ["稻瘟病", "纹枯病", "白叶枯病", "稻曲病"],
    "小麦": ["小麦锈病", "小麦赤霉病", "小麦白粉病", "小麦纹枯病", "小麦全蚀病"],
    "玉米": ["玉米大斑病", "玉米小斑病", "玉米锈病", "玉米黑穗病", "玉米茎基腐病"],
    "大豆": ["大豆锈病", "大豆炭疽病", "大豆疫病", "大豆紫斑病"],
    "马铃薯": ["马铃薯晚疫病", "马铃薯早疫病", "马铃薯疮痂病", "马铃薯病毒病"],
    "甘薯": ["甘薯黑斑病", "甘薯软腐病", "甘薯病毒病"],

    # 茄果类
    "番茄": ["番茄早疫病", "番茄晚疫病", "番茄灰霉病", "番茄叶霉病", "番茄病毒病", "番茄青枯病", "番茄炭疽病",
             "番茄脐腐病"],
    "辣椒": ["辣椒炭疽病", "辣椒疫病", "辣椒病毒病", "辣椒白粉病", "辣椒疮痂病"],
    "茄子": ["茄子黄萎病", "茄子褐纹病", "茄子绵疫病", "茄子炭疽病"],

    # 瓜类
    "黄瓜": ["黄瓜白粉病", "黄瓜霜霉病", "黄瓜角斑病", "黄瓜枯萎病", "黄瓜蔓枯病", "黄瓜炭疽病", "黄瓜病毒病"],
    "西瓜": ["西瓜炭疽病", "西瓜枯萎病", "西瓜病毒病", "西瓜白粉病", "西瓜蔓枯病"],
    "甜瓜": ["甜瓜霜霉病", "甜瓜白粉病", "甜瓜枯萎病", "甜瓜病毒病"],
    "南瓜": ["南瓜白粉病", "南瓜霜霉病", "南瓜病毒病", "南瓜炭疽病"],
    "冬瓜": ["冬瓜疫病", "冬瓜炭疽病", "冬瓜白粉病"],

    # 叶菜类
    "白菜": ["白菜软腐病", "白菜霜霉病", "白菜病毒病", "白菜黑斑病", "白菜白斑病"],
    "菠菜": ["菠菜霜霉病", "菠菜炭疽病", "菠菜病毒病", "菠菜白锈病"],
    "生菜": ["生菜灰霉病", "生菜霜霉病", "生菜菌核病", "生菜病毒病"],
    "芹菜": ["芹菜斑枯病", "芹菜叶斑病", "芹菜病毒病", "芹菜软腐病"],
    "油菜": ["油菜霜霉病", "油菜病毒病", "油菜白锈病", "油菜菌核病"],
    "韭菜": ["韭菜灰霉病", "韭菜锈病", "韭菜疫病"],

    # 果树类
    "苹果": ["苹果轮纹病", "苹果炭疽病", "苹果锈病", "苹果褐斑病", "苹果白粉病", "苹果腐烂病"],
    "梨": ["梨锈病", "梨黑星病", "梨轮纹病", "梨褐斑病", "梨腐烂病"],
    "桃": ["桃缩叶病", "桃褐腐病", "桃穿孔病", "桃炭疽病", "桃流胶病"],
    "葡萄": ["葡萄霜霉病", "葡萄白粉病", "葡萄炭疽病", "葡萄黑痘病", "葡萄灰霉病", "葡萄褐斑病"],
    "草莓": ["草莓灰霉病", "草莓白粉病", "草莓炭疽病", "草莓根腐病", "草莓病毒病"],
    "石榴": ["石榴干腐病", "石榴褐斑病", "石榴炭疽病", "石榴麻皮病"],
    "香蕉": ["香蕉叶斑病", "香蕉炭疽病", "香蕉枯萎病", "香蕉束顶病"],
    "柑橘": ["柑橘炭疽病", "柑橘疮痂病", "柑橘黄龙病", "柑橘溃疡病", "柑橘青霉病"],

    # 豆类
    "豆角": ["豆角锈病", "豆角炭疽病", "豆角枯萎病", "豆角疫病", "豆角煤霉病"],
    "豇豆": ["豆角锈病", "豆角炭疽病", "豆角枯萎病"],
    "豌豆": ["豌豆白粉病", "豌豆锈病", "豌豆褐斑病"],

    # 葱蒜类
    "大葱": ["大葱锈病", "大葱霜霉病", "大葱紫斑病", "大葱黑斑病"],
    "大蒜": ["大蒜叶枯病", "大蒜锈病", "大蒜白腐病", "大蒜病毒病"],
    "洋葱": ["洋葱锈病", "洋葱霜霉病", "洋葱黑斑病", "洋葱软腐病"],

    # 薯类
    "甘薯": ["甘薯黑斑病", "甘薯软腐病", "甘薯病毒病", "甘薯茎腐病"]
}

# ==================== 病害症状详细描述库（扩展版） ====================
DISEASE_SYMPTOMS_DETAIL = {
    # 小麦病害
    "小麦锈病": {
        "zh": "叶片出现铁锈色条状斑点，破裂后散出褐色粉末。有条锈（条状）、叶锈（圆形）、秆锈（大斑）三种类型。严重时叶片布满病斑，影响光合作用，导致减产。",
        "en": "Rust-colored strip spots on leaves, releasing brown powder when ruptured. Three types: stripe rust (strip), leaf rust (circular), stem rust (large lesions). Severe infection covers leaves with lesions, affecting photosynthesis and reducing yield."
    },
    "小麦赤霉病": {
        "zh": "穗部出现粉红色霉层，后期产生黑色颗粒。病粒有毒，人畜不可食。抽穗扬花期遇雨易发病，严重时可导致绝收。",
        "en": "Pink mold on spikes, later producing black granules. Infected grains are toxic, not edible. Disease occurs easily when rain during heading and flowering, may cause total crop loss in severe cases."
    },
    "小麦白粉病": {
        "zh": "叶片表面出现白色粉状霉层，后期霉层变灰褐色，叶片黄化干枯。从下部叶片向上发展，严重时植株矮小。",
        "en": "White powdery mildew on leaf surface, later turning gray-brown, leaves yellow and wither. Progresses from lower leaves upward, plants may be stunted in severe cases."
    },
    "小麦纹枯病": {
        "zh": "茎基部出现椭圆形或云纹状病斑，边缘褐色，中间灰白色。后期病斑环绕茎秆，导致倒伏或枯死。",
        "en": "Elliptical or cloud-shaped lesions on stem base, brown edges, gray-white center. Lesions may girdle stem later, causing lodging or death."
    },
    "小麦全蚀病": {
        "zh": "根系和茎基部变黑腐烂，植株矮小，早枯。拔起病株可见根部表面有黑色菌丝层。",
        "en": "Roots and stem base turn black and rot, plants stunted and die early. Black mycelial layer visible on root surface when pulling up diseased plants."
    },

    # 玉米病害
    "玉米大斑病": {
        "zh": "叶片出现长梭形大斑，中央灰褐色，边缘深褐色，潮湿时病斑有黑色霉层。先从下部叶片发病，逐渐向上扩展。",
        "en": "Large spindle-shaped lesions on leaves, gray-brown center, dark brown edges, black mold under humid conditions. Starts from lower leaves, gradually spreads upward."
    },
    "玉米小斑病": {
        "zh": "叶片出现椭圆形小斑，边缘赤褐色，有同心轮纹。病斑较小但数量多，可连片形成大斑。",
        "en": "Small oval lesions on leaves, reddish-brown edges, with concentric rings. Lesions are small but numerous, may coalesce into large patches."
    },
    "玉米锈病": {
        "zh": "叶片两面散生或聚生褐色夏孢子堆，破裂后散出锈色粉末。后期产生黑褐色冬孢子堆。",
        "en": "Brown uredinia scattered or clustered on both leaf surfaces, releasing rust-colored powder when ruptured. Dark brown telia produced later."
    },
    "玉米黑穗病": {
        "zh": "雄穗或雌穗变成黑色粉状孢子堆，外包白膜，破裂后散出黑粉。病株常矮化。",
        "en": "Male or female tassels turn into black powdery spore masses, wrapped in white membrane, releasing black powder when ruptured. Plants often stunted."
    },

    # 水稻病害
    "稻瘟病": {
        "zh": "叶片出现梭形病斑，中央灰白色，边缘褐色，潮湿时有灰色霉层。严重时叶节、穗颈受害，形成白穗。",
        "en": "Spindle-shaped lesions on leaves, gray-white center, brown edges, gray mold under humid conditions. Nodes and panicle necks affected in severe cases, causing white heads."
    },
    "纹枯病": {
        "zh": "叶鞘出现云纹状病斑，边缘褐色，中间灰白色，后期病斑融合，叶片枯死。",
        "en": "Cloud-shaped lesions on leaf sheaths, brown edges, gray-white center, lesions coalesce later, leaves die."
    },
    "白叶枯病": {
        "zh": "叶尖或叶缘出现黄绿色病斑，沿叶脉向下扩展，病斑边缘波纹状，后期灰白色。",
        "en": "Yellow-green lesions at leaf tips or margins, extending downward along veins, wavy lesion edges, later gray-white."
    },

    # 番茄病害
    "番茄早疫病": {
        "zh": "叶片出现同心轮纹状褐色病斑，像靶子一样，周围有黄色晕圈。茎部病斑椭圆形，褐色，稍凹陷。",
        "en": "Brown concentric ring lesions on leaves, like a target, with yellow halo. Oval brown slightly sunken lesions on stems."
    },
    "番茄晚疫病": {
        "zh": "叶片出现暗绿色水渍状病斑，像被水泡过，潮湿时边缘长出白色霉层。果实出现褐色硬斑，表面粗糙。",
        "en": "Dark green water-soaked lesions on leaves, like soaked in water, white mold on edges under humid conditions. Brown hard spots on fruits, rough surface."
    },
    "番茄灰霉病": {
        "zh": "果实和花器出现灰色霉层，像灰色绒毛，病部软腐。叶片出现V字形病斑，从叶缘向内发展。",
        "en": "Gray mold on fruits and flowers, like gray velvet, soft rot. V-shaped lesions on leaves, progressing inward from leaf margins."
    },
    "番茄叶霉病": {
        "zh": "叶片背面出现灰紫色天鹅绒状霉层，正面出现黄色病斑。严重时叶片卷曲干枯，霉层布满叶背。",
        "en": "Gray-purple velvety mold on underside of leaves, yellow lesions on upper surface. Leaves may curl and wither in severe cases, mold covers entire underside."
    },
    "番茄病毒病": {
        "zh": "叶片出现花叶、蕨叶、条斑等症状，植株矮化，果实畸形。由蚜虫传播。",
        "en": "Mosaic, fern leaf, streak symptoms on leaves, stunted plants, deformed fruits. Transmitted by aphids."
    },
    "番茄青枯病": {
        "zh": "植株白天萎蔫，傍晚恢复，几天后枯死。茎部维管束变褐，挤压有白色菌脓。",
        "en": "Plants wilt during day, recover in evening, die within days. Brown vascular bundles in stem, white bacterial ooze when squeezed."
    },
    "番茄炭疽病": {
        "zh": "果实出现圆形凹陷斑，有同心轮纹，表面有黑色小点，湿度大时有粉红色黏状物。",
        "en": "Circular sunken spots on fruits, with concentric rings, black dots on surface, pink sticky substance under high humidity."
    },
    "番茄脐腐病": {
        "zh": "果实脐部出现水渍状暗绿色病斑，后扩大为黑褐色凹陷斑，果皮革质。生理性病害，缺钙引起。",
        "en": "Water-soaked dark green lesions at fruit blossom end, later expanding into black-brown sunken spots, leathery skin. Physiological disorder caused by calcium deficiency."
    },

    # 黄瓜病害
    "黄瓜白粉病": {
        "zh": "叶片表面出现白色粉状霉斑，像撒了面粉，初期为小粉斑，后期扩大连片，叶片黄化干枯。",
        "en": "White powdery mildew spots on leaf surface, like flour, small spots initially, later expand and coalesce, leaves yellow and wither."
    },
    "黄瓜霜霉病": {
        "zh": "叶片出现多角形黄褐色病斑，受叶脉限制，背面有灰黑色霜状霉层。病斑从下部叶片开始向上发展。",
        "en": "Angular yellow-brown lesions on leaves, limited by veins, gray-black downy mold on underside. Lesions start from lower leaves upward."
    },
    "黄瓜角斑病": {
        "zh": "叶片出现多角形水渍状病斑，受叶脉限制，后期病斑灰白色，易穿孔。潮湿时背面有乳白色菌脓。",
        "en": "Angular water-soaked lesions on leaves, limited by veins, later turning gray-white, easily perforated. Milky white bacterial ooze on underside under humid conditions."
    },
    "黄瓜枯萎病": {
        "zh": "植株白天萎蔫，早晚恢复，几天后枯死。茎基部纵裂，维管束变褐，潮湿时产生粉红色霉层。",
        "en": "Plants wilt during day, recover at night, die within days. Longitudinal cracks at stem base, brown vascular bundles, pink mold under humid conditions."
    },
    "黄瓜蔓枯病": {
        "zh": "茎蔓出现椭圆形或梭形病斑，灰褐色，有琥珀色胶状物。叶片出现V字形病斑。",
        "en": "Elliptical or spindle-shaped lesions on vines, gray-brown, with amber-colored gum. V-shaped lesions on leaves."
    },

    # 草莓病害
    "草莓灰霉病": {
        "zh": "果实出现灰色霉层，病部软腐，萼片出现褐色病斑。病果表面密生灰色霉层，最终干缩。",
        "en": "Gray mold on fruits, soft rot, brown lesions on sepals. Diseased fruits covered with gray mold, eventually dry and shrink."
    },
    "草莓白粉病": {
        "zh": "叶片背面出现白色粉状霉层，叶片边缘向上卷曲呈匙形。果实受害时表面覆白色粉层。",
        "en": "White powdery mildew on underside of leaves, leaf edges curl upward like a spoon. Fruits covered with white powder when affected."
    },
    "草莓炭疽病": {
        "zh": "叶柄和匍匐茎出现黑色凹陷病斑，病斑环绕时上部萎蔫死亡。根茎部横切可见褐变。",
        "en": "Black sunken lesions on petioles and stolons, upper part wilts and dies when lesions girdle. Brown discoloration visible in crown cross-section."
    },
    "草莓根腐病": {
        "zh": "植株生长不良，叶片黄化萎蔫，根系变褐腐烂，易拔起。",
        "en": "Poor plant growth, leaves yellow and wilt, roots turn brown and rot, easily pulled up."
    },

    # 葡萄病害
    "葡萄霜霉病": {
        "zh": "叶片出现多角形黄褐色病斑，背面有白色霜状霉层。幼果受害时表面生白色霉层，后期皱缩脱落。",
        "en": "Angular yellow-brown lesions on leaves, white downy mold on underside. Young fruits covered with white mold, later shrink and drop."
    },
    "葡萄白粉病": {
        "zh": "叶片、果实表面出现灰白色粉状物，受害叶片卷缩干枯，果实表面形成网状纹路，后期开裂。",
        "en": "Gray-white powdery mildew on leaves and fruit surface, affected leaves curl and wither, net-like patterns on fruit surface, later cracking."
    },
    "葡萄炭疽病": {
        "zh": "果实出现圆形凹陷斑，有同心轮纹，表面有粉红色黏稠物，病斑可扩大连片。",
        "en": "Circular sunken spots on fruits, with concentric rings, pink sticky substance, lesions may coalesce."
    },
    "葡萄黑痘病": {
        "zh": "叶片出现圆形褐色病斑，边缘暗褐色，中央灰白色，后期穿孔。果实出现鸟眼状病斑。",
        "en": "Circular brown lesions on leaves, dark brown edges, gray-white center, later perforated. Bird's eye spots on fruits."
    },

    # 苹果病害
    "苹果轮纹病": {
        "zh": "枝干出现圆形瘤状突起，边缘开裂。果实出现褐色轮纹斑，病斑软腐，表面有黑色小点。",
        "en": "Circular wart-like protrusions on branches, edges cracking. Brown ring spots on fruits, soft rot, with black dots on surface."
    },
    "苹果炭疽病": {
        "zh": "果实出现褐色圆形病斑，病斑凹陷，表面有黑色小点呈同心轮纹状排列。病果腐烂，有酒糟味。",
        "en": "Brown circular lesions on fruits, sunken, with black dots arranged in concentric rings. Diseased fruits rot, with alcoholic odor."
    },
    "苹果锈病": {
        "zh": "叶片正面出现橙黄色圆形病斑，上有黑色小点。背面长出毛状物（锈孢子器）。",
        "en": "Orange-yellow circular lesions on upper leaf surface, with black dots. Hair-like structures (aecia) on underside."
    },
    "苹果褐斑病": {
        "zh": "叶片出现褐色斑点，周围有绿色晕圈，病斑融合后叶片黄化早落。",
        "en": "Brown spots on leaves, with green halo, lesions coalesce causing yellowing and premature leaf drop."
    },

    # 石榴病害
    "石榴干腐病": {
        "zh": "果实出现褐色腐烂斑块，表面有黑色小点，病斑扩大后果实干缩。枝干出现凹陷病斑，树皮开裂。",
        "en": "Brown rot patches on fruits, with black dots on surface, fruits shrink as lesions expand. Sunken lesions on branches, bark cracking."
    },
    "石榴褐斑病": {
        "zh": "叶片出现圆形或多角形褐色病斑，后期病斑融合，叶片早落。",
        "en": "Circular or angular brown lesions on leaves, later lesions coalesce, leaves drop prematurely."
    }
}

# ==================== 病害特征库（简化版，只用于颜色匹配） ====================
DISEASE_FEATURES = {
    # 白粉病类
    "小麦白粉病": {
        "color_ranges": [
            {"name": "白色", "rgb": [(220, 220, 220), (255, 255, 255)], "weight": 0.7},
            {"name": "灰白色", "rgb": [(180, 180, 180), (220, 220, 220)], "weight": 0.2}
        ],
        "possible_crops": ["小麦"]
    },
    "黄瓜白粉病": {
        "color_ranges": [
            {"name": "白色", "rgb": [(220, 220, 220), (255, 255, 255)], "weight": 0.7},
            {"name": "灰白色", "rgb": [(180, 180, 180), (220, 220, 220)], "weight": 0.2}
        ],
        "possible_crops": ["黄瓜", "南瓜", "甜瓜"]
    },
    "草莓白粉病": {
        "color_ranges": [
            {"name": "白色", "rgb": [(220, 220, 220), (255, 255, 255)], "weight": 0.6},
            {"name": "灰白色", "rgb": [(180, 180, 180), (220, 220, 220)], "weight": 0.2}
        ],
        "possible_crops": ["草莓"]
    },

    # 霜霉病类
    "黄瓜霜霉病": {
        "color_ranges": [
            {"name": "黄褐色", "rgb": [(160, 120, 60), (220, 180, 100)], "weight": 0.4},
            {"name": "灰黑色", "rgb": [(80, 80, 80), (150, 150, 150)], "weight": 0.3}
        ],
        "possible_crops": ["黄瓜", "甜瓜"]
    },
    "葡萄霜霉病": {
        "color_ranges": [
            {"name": "黄褐色", "rgb": [(160, 120, 50), (220, 170, 80)], "weight": 0.4},
            {"name": "白色", "rgb": [(220, 220, 220), (250, 250, 250)], "weight": 0.3}
        ],
        "possible_crops": ["葡萄"]
    },

    # 锈病类
    "小麦锈病": {
        "color_ranges": [
            {"name": "铁锈色", "rgb": [(150, 80, 30), (220, 150, 80)], "weight": 0.6},
            {"name": "褐色", "rgb": [(100, 50, 20), (160, 100, 50)], "weight": 0.2}
        ],
        "possible_crops": ["小麦", "大麦"]
    },
    "豆角锈病": {
        "color_ranges": [
            {"name": "铁锈色", "rgb": [(150, 80, 30), (220, 150, 80)], "weight": 0.7},
            {"name": "褐色", "rgb": [(100, 50, 20), (160, 100, 50)], "weight": 0.2}
        ],
        "possible_crops": ["豆角", "豇豆"]
    },

    # 炭疽病类
    "辣椒炭疽病": {
        "color_ranges": [
            {"name": "黑褐色", "rgb": [(40, 20, 10), (100, 60, 30)], "weight": 0.4},
            {"name": "红褐色", "rgb": [(120, 40, 20), (180, 80, 50)], "weight": 0.3}
        ],
        "possible_crops": ["辣椒"]
    },
    "西瓜炭疽病": {
        "color_ranges": [
            {"name": "黑褐色", "rgb": [(40, 20, 10), (100, 60, 30)], "weight": 0.4},
            {"name": "褐色", "rgb": [(80, 40, 20), (150, 90, 50)], "weight": 0.3}
        ],
        "possible_crops": ["西瓜"]
    },

    # 早疫病类
    "番茄早疫病": {
        "color_ranges": [
            {"name": "褐色同心轮纹", "rgb": [(100, 50, 20), (160, 100, 60)], "weight": 0.6}
        ],
        "possible_crops": ["番茄", "马铃薯"]
    },

    # 晚疫病类
    "番茄晚疫病": {
        "color_ranges": [
            {"name": "暗绿色", "rgb": [(50, 80, 50), (100, 150, 100)], "weight": 0.4},
            {"name": "暗褐色", "rgb": [(60, 40, 20), (120, 80, 50)], "weight": 0.3}
        ],
        "possible_crops": ["番茄", "马铃薯"]
    },
    "马铃薯晚疫病": {
        "color_ranges": [
            {"name": "暗褐色", "rgb": [(60, 40, 20), (120, 80, 50)], "weight": 0.4},
            {"name": "暗绿色", "rgb": [(50, 80, 50), (100, 150, 100)], "weight": 0.3}
        ],
        "possible_crops": ["马铃薯", "番茄"]
    },

    # 灰霉病类
    "番茄灰霉病": {
        "color_ranges": [
            {"name": "灰色", "rgb": [(150, 150, 150), (220, 220, 220)], "weight": 0.6},
            {"name": "灰褐色", "rgb": [(120, 100, 80), (180, 150, 120)], "weight": 0.2}
        ],
        "possible_crops": ["番茄", "草莓", "黄瓜"]
    },
    "草莓灰霉病": {
        "color_ranges": [
            {"name": "灰色", "rgb": [(150, 150, 150), (220, 220, 220)], "weight": 0.6},
            {"name": "灰褐色", "rgb": [(120, 100, 80), (180, 150, 120)], "weight": 0.2}
        ],
        "possible_crops": ["草莓"]
    }
}


# ==================== 图像分析函数（简化版） ====================

def analyze_image_features(image_path):
    """分析图像特征"""
    try:
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')

        pixels = list(img.getdata())
        if len(pixels) > 50000:
            step = len(pixels) // 50000
            pixels = pixels[::step]

        # 颜色分布分析
        color_ratios = {}
        color_ranges = {
            'white': [(220, 220, 220), (255, 255, 255)],
            'off_white': [(180, 180, 180), (220, 220, 220)],
            'gray': [(150, 150, 150), (180, 180, 180)],
            'dark_gray': [(100, 100, 100), (150, 150, 150)],
            'black': [(0, 0, 0), (80, 80, 80)],
            'brown': [(80, 40, 20), (160, 100, 60)],
            'dark_brown': [(40, 20, 10), (100, 60, 30)],
            'rust': [(150, 80, 30), (220, 150, 80)],
            'yellow_brown': [(160, 120, 50), (230, 190, 100)],
            'dark_green': [(0, 40, 0), (60, 120, 60)]
        }

        for color_name, (low, high) in color_ranges.items():
            count = 0
            for r, g, b in pixels:
                if (low[0] <= r <= high[0] and
                        low[1] <= g <= high[1] and
                        low[2] <= b <= high[2]):
                    count += 1
            ratio = (count / len(pixels)) * 100
            color_ratios[color_name] = ratio

        return {'color_ratios': color_ratios}

    except Exception as e:
        print(f"图像分析失败: {e}")
        return None


def extract_crop_from_name(name):
    """智能提取作物名称（加强版）"""
    if not name or name == "未知":
        return "未知作物"

    # 完整作物列表
    crop_keywords = {
        "水稻": ["水稻", "稻谷", "稻", "rice"],
        "小麦": ["小麦", "麦子", "麦", "wheat"],
        "玉米": ["玉米", "包谷", "苞谷", "corn", "maize"],
        "大豆": ["大豆", "黄豆", "soybean"],
        "马铃薯": ["马铃薯", "土豆", "洋芋", "potato"],
        "甘薯": ["甘薯", "红薯", "地瓜", "sweet potato"],
        "番茄": ["番茄", "西红柿", "tomato"],
        "辣椒": ["辣椒", "甜椒", "chili", "pepper"],
        "茄子": ["茄子", "eggplant"],
        "黄瓜": ["黄瓜", "青瓜", "cucumber"],
        "西瓜": ["西瓜", "watermelon"],
        "甜瓜": ["甜瓜", "香瓜", "melon"],
        "南瓜": ["南瓜", "倭瓜", "pumpkin"],
        "白菜": ["白菜", "大白菜", "cabbage"],
        "菠菜": ["菠菜", "spinach"],
        "生菜": ["生菜", "lettuce"],
        "芹菜": ["芹菜", "celery"],
        "油菜": ["油菜", "青菜", "bok choy"],
        "韭菜": ["韭菜", "leek"],
        "苹果": ["苹果", "apple"],
        "梨": ["梨", "pear"],
        "桃": ["桃", "桃子", "peach"],
        "葡萄": ["葡萄", "grape"],
        "草莓": ["草莓", "strawberry"],
        "石榴": ["石榴", "pomegranate"],
        "香蕉": ["香蕉", "banana"],
        "橙子": ["橙子", "orange", "柑橘"],
        "豆角": ["豆角", "豇豆", "bean"],
        "大葱": ["大葱", "葱", "green onion"],
        "大蒜": ["大蒜", "蒜", "garlic"],
        "洋葱": ["洋葱", "onion"]
    }

    name_lower = name.lower()

    # 优先精确匹配
    for crop, keywords in crop_keywords.items():
        for keyword in keywords:
            if keyword in name or keyword in name_lower:
                return crop

    return "未知作物"


def recognize_with_baidu(image_path):
    """调用百度AI识别"""
    if client is None:
        return {"error": "百度AI未初始化"}
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        result = client.plantDetect(image_data, {'baike_num': 5})
        if not result.get('result'):
            result = client.advancedGeneral(image_data, {'baike_num': 5})
        if 'error_code' in result:
            return {"error": f"API错误: {result.get('error_msg', '')}"}
        if result.get('result'):
            top = result['result'][0]
            name = top.get('name') or top.get('keyword', '')
            score = top.get('score', 0)
            baike_url = top.get('baike_info', {}).get('baike_url', '') if 'baike_info' in top else ''
            return {
                'name': name,
                'score': round(score, 2),
                'baike_url': baike_url,
                'raw_result': result['result']
            }
        return {"error": "未能识别"}
    except Exception as e:
        return {"error": f"识别异常: {str(e)}"}


def get_cache_key(image_path):
    with open(image_path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def get_cached_result(image_path):
    cache_key = get_cache_key(image_path)
    cache_file = os.path.join(app.config['CACHE_FOLDER'], f"{cache_key}.pkl")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except:
            return None
    return None


def save_cache(image_path, result):
    cache_key = get_cache_key(image_path)
    cache_file = os.path.join(app.config['CACHE_FOLDER'], f"{cache_key}.pkl")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(result, f)
    except:
        pass


def get_crop_info(recognized_name, mode='food', image_path=None):
    """获取作物信息（强制作物关联版）"""
    print(f"🔍 识别: {recognized_name}, 模式: {mode}")

    # 提取作物名称
    detected_crop = extract_crop_from_name(recognized_name)
    print(f"🌾 提取到作物: {detected_crop}")

    # 病害模式
    if mode == 'disease':
        # 分析图像特征
        image_features = None
        if image_path:
            image_features = analyze_image_features(image_path)

        # 如果识别到具体作物，只返回该作物的病害
        if detected_crop != "未知作物":
            # 获取该作物可能的所有病害
            possible_diseases = CROP_DISEASE_STRICT.get(detected_crop, [])

            if possible_diseases:
                # 如果有图像特征，尝试匹配具体病害
                if image_features and image_features.get('color_ratios'):
                    color_ratios = image_features['color_ratios']

                    # 遍历该作物的所有病害，计算匹配度
                    disease_scores = []
                    for disease in possible_diseases:
                        if disease in DISEASE_FEATURES:
                            features = DISEASE_FEATURES[disease]
                            score = 0
                            weight_sum = 0

                            for color_range in features["color_ranges"]:
                                range_name = color_range["name"]
                                weight = color_range["weight"]

                                color_map = {
                                    "白色": "white",
                                    "灰白色": "off_white",
                                    "灰色": "gray",
                                    "铁锈色": "rust",
                                    "褐色": "brown",
                                    "黄褐色": "yellow_brown",
                                    "黑褐色": "dark_brown",
                                    "暗绿色": "dark_green",
                                    "暗褐色": "dark_brown"
                                }

                                eng_name = color_map.get(range_name, range_name)
                                ratio = color_ratios.get(eng_name, 0)

                                if ratio > 0.5:
                                    range_score = min(ratio / 5, 1.0) * 100
                                    score += range_score * weight
                                    weight_sum += weight

                            if weight_sum > 0:
                                final_score = score / weight_sum
                                if final_score > 20:
                                    disease_scores.append((disease, final_score))

                    if disease_scores:
                        # 按分数排序
                        disease_scores.sort(key=lambda x: x[1], reverse=True)
                        top_disease = disease_scores[0][0]
                        confidence = min(round(disease_scores[0][1], 2), 95.0)

                        # 获取病害详细信息
                        if top_disease in DISEASE_KNOWLEDGE:
                            info = DISEASE_KNOWLEDGE[top_disease].copy()
                        else:
                            info = {
                                'crop': detected_crop,
                                'crop_en': detected_crop,
                                'symptoms': '请咨询当地农技站获取详细症状描述。',
                                'symptoms_en': 'Consult local agricultural extension for detailed symptoms.',
                                'treatment': '建议咨询当地农技站获取具体防治方案。',
                                'treatment_en': 'Consult local agricultural extension for specific treatment.',
                                'prevention': '加强田间管理，合理施肥，及时清除病株。',
                                'prevention_en': 'Strengthen field management, fertilize properly, remove diseased plants promptly.'
                            }

                        # 添加详细症状
                        symptoms_detail = DISEASE_SYMPTOMS_DETAIL.get(top_disease, {})
                        symptoms_zh = symptoms_detail.get('zh', '')
                        symptoms_en = symptoms_detail.get('en', '')

                        result_info = {
                            'type': 'disease',
                            'matched_disease': top_disease,
                            'detected_crop': detected_crop,
                            'crop': info.get('crop', detected_crop),
                            'crop_en': info.get('crop_en', detected_crop),
                            'symptoms': info.get('symptoms', '') + (
                                '\n\n详细症状：' + symptoms_zh if symptoms_zh else ''),
                            'symptoms_en': info.get('symptoms_en', '') + (
                                '\n\nDetailed symptoms: ' + symptoms_en if symptoms_en else ''),
                            'treatment': info.get('treatment', '建议咨询当地农技站'),
                            'treatment_en': info.get('treatment_en', 'Consult local agricultural extension'),
                            'prevention': info.get('prevention', '加强田间管理'),
                            'prevention_en': info.get('prevention_en', 'Strengthen field management'),
                            'confidence': confidence
                        }
                        return result_info

                # 如果没有匹配到具体病害，返回该作物的通用病害信息
                # 返回第一个病害作为默认
                default_disease = possible_diseases[0]
                if default_disease in DISEASE_KNOWLEDGE:
                    info = DISEASE_KNOWLEDGE[default_disease].copy()
                else:
                    info = {
                        'crop': detected_crop,
                        'crop_en': detected_crop,
                        'symptoms': '请上传更清晰的病斑照片以便准确识别。',
                        'symptoms_en': 'Please upload clearer photos of lesions for accurate identification.',
                        'treatment': '建议咨询当地农技站获取具体防治方案。',
                        'treatment_en': 'Consult local agricultural extension for specific treatment.',
                        'prevention': '加强田间管理，合理施肥，及时清除病株。',
                        'prevention_en': 'Strengthen field management, fertilize properly, remove diseased plants promptly.'
                    }

                symptoms_detail = DISEASE_SYMPTOMS_DETAIL.get(default_disease, {})
                symptoms_zh = symptoms_detail.get('zh', '')
                symptoms_en = symptoms_detail.get('en', '')

                return {
                    'type': 'disease',
                    'matched_disease': default_disease,
                    'detected_crop': detected_crop,
                    'crop': info.get('crop', detected_crop),
                    'crop_en': info.get('crop_en', detected_crop),
                    'symptoms': info.get('symptoms', '') + ('\n\n详细症状：' + symptoms_zh if symptoms_zh else ''),
                    'symptoms_en': info.get('symptoms_en', '') + (
                        '\n\nDetailed symptoms: ' + symptoms_en if symptoms_en else ''),
                    'treatment': info.get('treatment', '建议咨询当地农技站'),
                    'treatment_en': info.get('treatment_en', 'Consult local agricultural extension'),
                    'prevention': info.get('prevention', '加强田间管理'),
                    'prevention_en': info.get('prevention_en', 'Strengthen field management'),
                    'confidence': 70.0
                }

        # 如果没有识别出作物，返回通用信息
        return {
            'type': 'disease',
            'matched_disease': '未知病害',
            'detected_crop': '未知作物',
            'crop': '未知作物',
            'crop_en': 'Unknown crop',
            'symptoms': '无法识别具体作物，请确保照片中包含叶片或果实。',
            'symptoms_en': 'Unable to identify specific crop, please ensure the photo contains leaves or fruits.',
            'treatment': '建议咨询当地农技站。',
            'treatment_en': 'Consult local agricultural extension.',
            'prevention': '加强田间管理。',
            'prevention_en': 'Strengthen field management.',
            'confidence': 30.0
        }

    # 食材模式
    # 映射到标准名
    std_name = NAME_MAPPING.get(recognized_name, recognized_name)

    # 检查食材
    if std_name in FOOD_KNOWLEDGE:
        info = FOOD_KNOWLEDGE[std_name].copy()
        info['type'] = 'food'
        return info

    # 默认返回
    return {
        'type': 'food',
        '科学名': 'Plantae',
        '英文名': 'Plant',
        '营养价值': '新鲜农产品富含维生素和矿物质。',
        'nutrition': 'Fresh produce is rich in vitamins and minerals.',
        '挑选方法': '选择新鲜、无损伤的农产品。',
        'selection': 'Choose fresh, undamaged produce.',
        '食用建议': '食用前充分清洗。',
        'usage': 'Wash thoroughly before eating.',
        '文化趣闻': '每一种农产品都有它独特的故事。',
        'culture': 'Every agricultural product has its unique story.'
    }


# ==================== 路由 ====================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/identify', methods=['POST'])
def identify():
    if 'image' not in request.files:
        return jsonify({'error': '没有上传图片'})

    file = request.files['image']
    if file.filename == '':
        return jsonify({'error': '未选择文件'})

    mode = request.form.get('mode', 'food')

    allowed = {'png', 'jpg', 'jpeg', 'bmp', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in allowed:
        return jsonify({'error': '不支持的文件格式'})

    try:
        timestamp = int(time.time())
        filename = f"{timestamp}_{file.filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # 检查缓存
        cached = get_cached_result(filepath)
        if cached:
            return jsonify(cached)

        # 调用百度识别
        baidu_result = recognize_with_baidu(filepath)

        recognized_name = "未知"
        baike_url = ""
        raw_results = []

        if 'error' not in baidu_result:
            recognized_name = baidu_result.get('name', '未知')
            baike_url = baidu_result.get('baike_url', '')
            raw_results = baidu_result.get('raw_result', [])

        # 获取作物信息
        crop_info = get_crop_info(recognized_name, mode, filepath)

        # 获取置信度
        confidence = 0
        if 'confidence' in crop_info:
            confidence = crop_info['confidence']
        elif 'error' not in baidu_result:
            confidence = baidu_result.get('score', 0)

        result = {
            'success': True,
            'recognized_name': recognized_name,
            'confidence': confidence,
            'baike_url': baike_url,
            'crop_info': crop_info,
            'raw_results': raw_results[:5]
        }

        save_cache(filepath, result)
        return jsonify(result)

    except Exception as e:
        return jsonify({'error': f'处理失败: {str(e)}'})


@app.route('/health')
def health():
    return jsonify({'status': 'ok'})


# ==================== 启动 ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = 'PORT' not in os.environ  # 生产环境自动关闭debug

    if debug_mode:
        print("=" * 60)
        print("🌱 农技百科 · 生产部署版")
        print("=" * 60)
        print(f"✅ 作物-病害严格关联：{len(CROP_DISEASE_STRICT)} 种作物")
        print(f"✅ 病害详细描述：{len(DISEASE_SYMPTOMS_DETAIL)} 种病害")
        print(f"✅ 服务地址: http://127.0.0.1:{port}")
        print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=debug_mode)