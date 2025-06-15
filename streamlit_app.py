import streamlit as st
import json
import os
import datetime
import pandas as pd
import math
from io import StringIO

# --------------------------------------------------
# ⚠️ Page config 必须是首个 Streamlit 调用
# --------------------------------------------------
st.set_page_config(
    page_title="精英网球巡回赛系统 Plus",
    layout="wide",
    initial_sidebar_state="expanded",
)

"""
精英网球巡回赛管理系统 － Plus 版
====================================
功能亮点（★为新增）
------------------
1. 赛事全流程：创建 → 录入比分 → 自动晋级 → 结算积分 → 排行榜 / 历史。
2. DOT 纯字符串可视化：移除 python‑graphviz 依赖。
3. ★ 选手管理：单个 / 批量导入、删除；扩展年龄、水平。
4. ★ Fast4 比分录入：三盘两胜，每盘局分实时记录。
5. ★ 数据导出：排行榜、历史 CSV 下载。
6. ★ 统计分析：参赛次数、淘汰轮胜率。
7. ★ 设置中心：查看并预留规则自定义。
"""

# --------------------------------------------------
# 1  常量与路径
# --------------------------------------------------
ICONS = {
    "home": "🏟️", "tournament": "🏆", "rankings": "📊", "history": "📜",
    "rules": "⚖️", "players": "👥", "stats": "📈", "settings": "🔧",
    "warning": "⚠️", "info": "ℹ️", "vs": "⚔️",
}

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
PLAYER_FILE   = os.path.join(DATA_DIR, "players.json")
RANKINGS_FILE = os.path.join(DATA_DIR, "rankings.json")
HISTORY_FILE  = os.path.join(DATA_DIR, "tournament_history.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# 默认设置（可手动编辑 settings.json）
DEFAULT_SETTINGS = {
    "fast4": {
        "sets_to_win": 2, "games_per_set": 4, "tiebreak_game": 3, "no_ad": True,
    },
    "points_structure": {
        "4":  {"winner":100,"finalist":60,"semifinalist":30},
        "8":  {"winner":200,"finalist":120,"semifinalist":70,"quarterfinalist":30},
        "16": {"winner":400,"finalist":240,"semifinalist":140,"quarterfinalist":80,"round_of_16":40},
        "32": {"winner":800,"finalist":480,"semifinalist":280,"quarterfinalist":160,"round_of_16":80,"round_of_32":40},
    },
}

# --------------------------------------------------
# 2  JSON I/O
# --------------------------------------------------

def load_json(path, fallback):
    if not os.path.exists(path):
        return fallback
    try:
        with open(path, "r", encoding="utf-8") as fp:
            return json.load(fp)
    except Exception:
        return fallback

def save_json(data, path):
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, ensure_ascii=False, indent=4)

# --------------------------------------------------
# 3  SessionState 初始化
# --------------------------------------------------
ss = st.session_state
ss.setdefault("page", "home")
ss.setdefault("tour_step", "setup")
ss.setdefault("tour_data", {})

# --------------------------------------------------
# 4  数据加载
# --------------------------------------------------
players_db   = load_json(PLAYER_FILE,   {})
rankings_db  = load_json(RANKINGS_FILE, {})
history_db   = load_json(HISTORY_FILE,  [])
settings_db  = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)

POINTS_STRUCTURE = {int(k): v for k, v in settings_db["points_structure"].items()}
FAST4            = settings_db["fast4"]

# --------------------------------------------------
# 5  工具函数：对阵 + DOT
# --------------------------------------------------

def next_pow2(n:int)->int: return 1 if n<=1 else 2**math.ceil(math.log2(n))

def make_bracket(seeds:list[str]):
    size  = next_pow2(len(seeds))
    byes  = seeds[:size-len(seeds)]
    rest  = seeds[len(byes):]
    match = [(rest[i], rest[~i]) for i in range(len(rest)//2)]
    return match, byes, size


def bracket_dot(td:dict)->str:
    if not td: return "digraph G {}"
    rds, size = td["rounds"], td["size"]
    lines=["digraph G {","rankdir=LR;",'node [shape=box,style="rounded,filled",fillcolor=lightblue,fontname=sans-serif];','edge [arrowhead=none];']
    champ=rds.get("1",[None])[0]
    if champ: lines.append(f'"R1_{champ}" [label="🏆 {champ}",fillcolor=gold];')
    cur=size
    while cur>=2:
        ps=rds.get(str(cur),[])
        for j in range(0,len(ps),2):
            p1,p2=ps[j], ps[j+1] if j+1<len(ps) else "BYE"
            nid=f"R{cur}_{j//2}"; lab=f"<{p1}<br/>⚔️<br/>{p2}>"
            lines.append(f'"{nid}" [label={lab}];')
            nxt=cur//2
            if nxt>=1 and champ:
                nxt_ps=rds.get(str(nxt),[])
                win=p1 if p1 in nxt_ps else p2 if p2 in nxt_ps else None
                if win:
                    target = f'"R1_{champ}"' if nxt==1 else f'"R{nxt}_{(j//2)//2}"'
                    lines.append(f'"{nid}" -> {target};')
        cur//=2
    lines.append("}")
    return "\n".join(lines)


def draw_bracket(td):
    st.graphviz_chart(bracket_dot(td), use_container_width=True)

# --------------------------------------------------
# 6  页面函数
# --------------------------------------------------
## 6.1 主页

def page_home():
    st.title(f"{ICONS['home']} 精英网球巡回赛系统 Plus")
    col1,col2,col3=st.columns(3)
    col1.metric("注册选手", len(players_db))
    col2.metric("累计比赛", len(history_db))
    col3.metric("上榜选手", len(rankings_db))
    st.info("左侧导航体验全部功能！")

## 6.2 赛事规则

def page_rules():
    st.title(f"{ICONS['rules']} 赛事规则")
    st.markdown("""### Fast4 概要\n- 三盘两胜；每盘 4 局胜；3‑3 抢七；40‑40 无占先。""")
    df=pd.DataFrame(POINTS_STRUCTURE).T.fillna("-")
    df.index.name="签位数"; st.dataframe(df,use_container_width=True)

## 6.3 选手管理

def page_players():
    st.title(f"{ICONS['players']} 选手管理")
    tab_add,tab_batch,tab_list=st.tabs(["单个添加","批量导入","列表"])
    with tab_add:
        with st.form("addform"):
            name=st.text_input("姓名"); age=st.number_input("年龄",5,80,18)
            level=st.selectbox("水平",["Rookie","Challenger","Pro"])
            ok=st.form_submit_button("添加")
        if ok:
            if not name or name in players_db:
                st.warning("姓名空或已存在")
            else:
                players_db[name]={"age":int(age),"level":level}; save_json(players_db,PLAYER_FILE); st.success("已添加"); st.experimental_rerun()
    with tab_batch:
        up=st.file_uploader("CSV 导入",type="csv")
        if up and st.button("导入"):
            df=pd.read_csv(StringIO(up.getvalue().decode()),header=None)
            added=0
            for _,row in df.iterrows():
                n,a,l=row[0],row[1],row[2]
                if n not in players_db:
                    players_db[n]={"age":int(a),"level":l}; added+=1
            save_json(players_db,PLAYER_FILE); st.success(f"导入 {added} 人"); st.experimental_rerun()
    with tab_list:
        if players_db:
            df=pd.DataFrame(players_db).T.reset_index().rename(columns={"index":"姓名"})
            st.dataframe(df,use_container_width=True)
            sel=st.multiselect("删除选手",list(players_db.keys()))
            if sel and st.button("删除"):
                for n in sel:
                    players_db.pop(n,None); rankings_db.pop(n,None)
                save_json(players_db,PLAYER_FILE); save_json(rankings_db,RANKINGS_FILE); st.success("已删除"); st.experimental_rerun()
        else:
            st.info("尚无选手")

## 6.4 比赛流程

def page_tournament():
    st.title(f"{ICONS['tournament']} 举办比赛")
    if ss.tour_step!="setup" and st.sidebar.button("取消当前比赛"):
        ss.tour_step,ss.tour_data="setup",{}
        st.experimental_rerun()
    # --- STEP1 设置 ---
    if ss.tour_step=="setup":
        seeds_txt=st.text_area("输入选手(一行一名,按种子)")
        if st.button("全部插入选手库") and players_db:
            seeds_txt="\n".join(players_db.keys()); st.experimental_rerun()
        seeds=[s.strip() for s in seeds_txt.strip().split("\n") if s.strip()] if seeds_txt else []
        if st.button("生成对阵",disabled=len(seeds)<2):
            matches,byes,size=make_bracket(seeds)
            ss.tour_data={"size":size,"rounds":{str(size):seeds},"current":byes+[p for m in matches for p in m]}
            ss.tour_step="playing"; st.experimental_rerun()
    # --- STEP2 比赛 ---
    elif ss.tour_step=="playing":
        td=ss.tour_data; cur=td["current"]; n=len(cur)
        st.subheader(f"{n} 强")
        draw_bracket(td)
        winners=[]
        for i in range(0,n,2):
            p1,p2=cur[i],cur[i+1]
            if p2=="BYE": winners.append(p1); continue
            col=st.columns(2); g1=col[0].number_input(f"{p1} 赢了几盘",0,FAST4["sets_to_win"],key=f"w{i}"); g2=col[1].number_input(f"{p2} 赢了几盘",0,FAST4["sets_to_win"],key=f"l{i}")
            if g1==FAST4["sets_to_win"]: winners.append(p1)
            elif g2==FAST4["sets_to_win"]: winners.append(p2)
        if len(winners)==n//2 and st.button("确认本轮"):
            td["rounds"][str(len(winners))]=winners; td["current"]=winners
            if len(winners)==1: ss.tour_step="finished"
            st.experimental_rerun()
    # --- STEP3 结束 ---
    elif ss.tour_step=="finished":
        td=ss.tour_data; champ=td["current"][0]
        st.success(f"🏆 冠军 {champ}"); draw_bracket(td); settle_points(td)
        if st.button("新比赛"):
            ss.tour_step="setup"; ss.tour_data={}; st.experimental_rerun()

## 6.5 积分榜

def page_rankings():
    st.title(f"{ICONS['rankings']} 积分榜")
    if not rankings_db: st.info("暂无数据"); return
    df=pd.Series(rankings_db).sort_values(ascending=False).reset_index(); df.columns=["姓名","积分"]; df["排名"]=range(1,len(df)+1)
    st.dataframe(df[["排名","姓名","积分"]],use_container_width=True)
    st.download_button("下载CSV",df.to_csv(index=False).encode(),"rankings.csv","text/csv")

## 6.6 历史

def page_history():
    st.title(f"{ICONS['history']} 历史记录")
    if not history_db: st.info("暂无记录"); return
    rec=[]
    for t in history_db:
        for p in t["participants"]:
            rec.append({"比赛":t["name"],"日期":t["id"].split()[0],"姓名":p["name"],"成绩":p["outcome"],"胜场":p["wins"],"积分":p["points_earned"]})
    df=pd.DataFrame(rec)
    st.dataframe
