import streamlit as st
import json, os, datetime, math, pandas as pd
from io import StringIO

# --------------------------------------------------
# 0️⃣  Page Config (首个 Streamlit 调用)
# --------------------------------------------------
st.set_page_config(
    page_title="精英网球巡回赛系统 Plus",
    layout="wide",
    initial_sidebar_state="expanded",
)

"""
精英网球巡回赛管理系统 Plus
=============================
★ 赛事全流程  ★ Fast4 比分录入  ★ 选手管理  ★ 数据导出  ★ 统计分析
"""

# --------------------------------------------------
# 1️⃣  路径 & 常量
# --------------------------------------------------
ICONS = {
    "home":"🏟️","tournament":"🏆","players":"👥","rankings":"📊",
    "history":"📜","stats":"📈","rules":"⚖️","settings":"🔧","vs":"⚔️",
}
DIR = "data"; os.makedirs(DIR, exist_ok=True)
PLAYER_F  = os.path.join(DIR,"players.json")
RANK_F    = os.path.join(DIR,"rankings.json")
HIST_F    = os.path.join(DIR,"history.json")
SET_F     = os.path.join(DIR,"settings.json")

DEFAULT = {
    "fast4": {"sets":2,"games":4},
    "points": {
        "4" :{"winner":100,"finalist":60,"semifinalist":30},
        "8" :{"winner":200,"finalist":120,"semifinalist":70,"quarterfinalist":30},
        "16":{"winner":400,"finalist":240,"semifinalist":140,"quarterfinalist":80,"round_of_16":40},
        "32":{"winner":800,"finalist":480,"semifinalist":280,"quarterfinalist":160,"round_of_16":80,"round_of_32":40},
    },
}

# --------------------------------------------------
# 2️⃣  JSON I/O
# --------------------------------------------------
ld = lambda p,d: json.load(open(p,'r',encoding='utf-8')) if os.path.exists(p) else d
dump = lambda d,p: json.dump(d,open(p,'w',encoding='utf-8'),ensure_ascii=False,indent=4)

players  = ld(PLAYER_F ,{})
rankings = ld(RANK_F   ,{})
history  = ld(HIST_F   ,[])
config   = ld(SET_F    ,DEFAULT)
FAST4    = config["fast4"]
POINTS   = {int(k):v for k,v in config["points"].items()}

ss=st.session_state; ss.setdefault("page","home"); ss.setdefault("step","setup"); ss.setdefault("tour",{})

# --------------------------------------------------
# 3️⃣  工具
# --------------------------------------------------
np2=lambda n:1 if n<=1 else 2**math.ceil(math.log2(n))

def build_bracket(seeds):
    size=np2(len(seeds)); byes=seeds[:size-len(seeds)]; rest=seeds[len(byes):]
    return [(rest[i],rest[~i]) for i in range(len(rest)//2)],byes,size

def dot_graph(t):
    if not t: return "digraph G {}"
    rd,sz=t["rounds"],t["size"]; champ=rd.get("1",[None])[0]
    g=["digraph G {","rankdir=LR;",'node [shape=box,style="rounded,filled",fillcolor=lightblue];','edge [arrowhead=none];']
    if champ:g.append(f'"C" [label="🏆 {champ}",fillcolor=gold];')
    cur=sz
    while cur>=2:
        pls=rd.get(str(cur),[])
        for j in range(0,len(pls),2):
            p1,p2=pls[j],pls[j+1] if j+1<len(pls) else "BYE"
            id=f"R{cur}_{j//2}"; g.append(f'"{id}" [label="{p1} {ICONS['vs']} {p2}"];')
            nxt=cur//2; target="C" if nxt==1 else f"R{nxt}_{(j//2)//2}"
            if champ: g.append(f'"{id}" -> "{target}";')
        cur//=2
    g.append("}"); return "\n".join(g)

def points_for(sz,outcome):
    key=min(POINTS,key=lambda k:abs(k-sz)); return POINTS[key].get(outcome,0)

# --------------------------------------------------
# 4️⃣  页面函数
# --------------------------------------------------

def home():
    st.title(f"{ICONS['home']} 精英网球巡回赛 Plus")
    c1,c2,c3=st.columns(3); c1.metric("选手",len(players)); c2.metric("比赛",len(history)); c3.metric("上榜",len(rankings))

# ---- 选手管理 ----

def players_page():
    st.title(f"{ICONS['players']} 选手管理")
    tab1,tab2,tab3=st.tabs(["添加","批量导入","列表"])
    with tab1:
        name=st.text_input("姓名"); age=st.number_input("年龄",5,80,18); lvl=st.selectbox("水平",["Rookie","Challenger","Pro"])
        if st.button("保存") and name and name not in players:
            players[name]={"age":int(age),"level":lvl}; dump(players,PLAYER_F); st.success("已添加"); st.experimental_rerun()
    with tab2:
        up=st.file_uploader("CSV name,age,level",type="csv")
        if up and st.button("导入"):
            df=pd.read_csv(StringIO(up.getvalue().decode()),header=None); added=0
            for _,r in df.iterrows():
                if r[0] not in players: players[r[0]]={"age":int(r[1]),"level":r[2]}; added+=1
            dump(players,PLAYER_F); st.success(f"导入{added}人"); st.experimental_rerun()
    with tab3:
        if players:
            df=pd.DataFrame(players).T.reset_index().rename(columns={"index":"姓名"})
            st.dataframe(df,use_container_width=True); sel=st.multiselect("删除",list(players))
            if sel and st.button("确认删除"):
                for n in sel: players.pop(n,None); rankings.pop(n,None)
                dump(players,PLAYER_F); dump(rankings,RANK_F); st.experimental_rerun()
        else: st.info("暂无选手")

# ---- 举办比赛 ----

def tour_page():
    st.title(f"{ICONS['tournament']} 举办比赛")
    if ss.step!="setup" and st.sidebar.button("取消比赛"):
        ss.step,ss.tour="setup",{}; st.experimental_rerun()
    if ss.step=="setup":
        seeds_txt=st.text_area("参赛队列(每行一名)")
        if st.button("用选手库填充"):
            seeds_txt="\n".join(players); st.experimental_rerun()
        seeds=[i.strip() for i in seeds_txt.split("\n") if i.strip()]
        if st.button("生成对阵",disabled=len(seeds)<2):
            m,byes,sz=build_bracket(seeds)
            ss.tour={"size":sz,"rounds":{str(sz):seeds},"current":byes+[p for a in m for p in a]}; ss.step="play"; st.experimental_rerun()
    elif ss.step=="play":
        td=ss.tour; cur=td["current"]; st.graphviz_chart(dot_graph(td))
        winners=[]
        for i in range(0,len(cur),2):
            p1,p2=cur[i],cur[i+1]; if p2=="BYE": winners.append(p1); continue
            c1,c2=st.columns(2); s1=c1.number_input(f"{p1} 赢盘",0,FAST4["sets"],key=f"a{i}"); s2=c2.number_input(f"{p2} 赢盘",0,FAST4["sets"],key=f"b{i}")
            if s1==FAST4["sets"]: winners.append(p1)
            elif s2==FAST4["sets"]: winners.append(p2)
        if len(winners)==len(cur)//2 and st.button("确认本轮"):
            td["rounds"][str(len(winners))]=winners; td["current"]=winners
            if len(winners)==1: ss.step="finish"; st.balloons()
            st.experimental_rerun()
    else:  # finish
        td=ss.tour; champ=td["current"][0]; st.success(f"冠军 {champ}"); st.graphviz_chart(dot_graph(td)); settle(td)
        if st.button("新比赛"): ss.step="setup"; ss.tour={}; st.experimental_rerun()

# ---- 积分 & 历史 ----

def rank_page():
    st.title(f"{ICONS['rankings']} 积分榜")
    if not rankings: st.info("暂无"); return
    df=pd.Series(rankings).sort_values(ascending=False).reset_index(); df.columns=["姓名","积分"]; df["排名"]=range(1,len(df)+1)
    st.dataframe(df,use_container_width=True); st.download_button("CSV",df.to_csv(index=False).encode(),"rankings.csv")

def hist_page():
    st.title(f"{ICONS['history']} 比赛历史")
    if not history: st.info("暂无"); return
    rec=[{**p,"比赛":h["name"],"日期":h["time"]} for h in history for p in h["players"]]
    df=pd.DataFrame(rec); st.dataframe(df,use_container_width=True); st.download_button("CSV",df.to_csv(index=False).encode(),"history.csv")

# ---- 统计 ----

def stats_page():
    st.title(f"{ICONS['stats']} 统计分析")
    if not history: st.info("暂无"); return
    names=set(rankings)
    name=st.selectbox("选手",sorted(names))
    played=sum(1 for h in history for p in h["players"] if p["name"]==name)
    st.write("参赛",played,"次, 积分",rankings.get(name,0))

# ---- 规则 & 设置 ----

settings_page=lambda: st.title(f"{ICONS['settings']} 设置中心")

# --------------------------------------------------
# 5️⃣  结算积分
# --------------------------------------------------

def settle(td):
    sz=td["size"]; ts=datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    rec={"time":ts,"name":f"{ts} ({sz}签)","players":[]};
    for p in td["rounds"][str(sz)]:
        outcome="参与"; for r in [1,2,4,8,16,32]:
            if p in td["rounds"].get(str(r),[]): outcome={1:"winner",2:"finalist",4:"semifinalist",8:"quarterfinalist",16:"round_of_16",32:"round_of_32"}[r]; break
        pts=points_for(sz,outcome); rankings[p]=rankings.get(p,0)+pts
        rec["players"].append({"name":p,"outcome":outcome,"wins":0,"points":pts})
    history.append(rec); dump(rankings,RANK_F); dump(history,HIST_F)

# --------------------------------------------------
# 6️⃣  路由 & Sidebar
# --------------------------------------------------
PAGES={"home":home,"tournament":tour_page,"players":players_page,"rankings":rank_page,"history":hist_page,"stats":stats_page,"rules":page_rules,"settings":settings_page}

for k,lab in [("home","主页"),("tournament","举办比赛"),("players","选手管理"),("rankings","积分榜"),("history","历史记录"),("stats","统计"),("rules","赛事规则"),("settings","设置")]:
    if st.sidebar.button(f"{ICONS.get(k,'')} {lab}"): ss.page=k

PAGES[ss.page]()
