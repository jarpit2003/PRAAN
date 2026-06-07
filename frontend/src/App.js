import { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, Tooltip, ResponsiveContainer, Legend,
} from "recharts";

const API  = "https://y353ks4bsq.us-east-1.awsapprunner.com";
const POLL = 10;

// ─────────────────────────────────────────────────────────
// Tokens
// ─────────────────────────────────────────────────────────
const T = {
  bg:      "#F4F6F9",
  card:    "#FFFFFF",
  border:  "#E2E8F0",
  sidebar: "#111827",
  sidebarBorder: "rgba(255,255,255,.07)",

  text:    "#0F172A",
  sub:     "#64748B",
  faint:   "#94A3B8",

  primary: "#2563EB",
  pLight:  "#EFF6FF",
  pDark:   "#1D4ED8",

  red:     "#DC2626",
  rLight:  "#FEF2F2",
  rBorder: "#FECACA",
  rDark:   "#B91C1C",

  amber:   "#D97706",
  aLight:  "#FFFBEB",

  green:   "#16A34A",
  gLight:  "#F0FDF4",
  gDark:   "#15803D",

  blue:    "#2563EB",
  bLight:  "#EFF6FF",

  purple:  "#7C3AED",
  purLight:"#F5F3FF",
};

const CHART = ["#3B82F6","#10B981","#F59E0B","#EF4444","#8B5CF6","#06B6D4","#EC4899","#14B8A6"];

const CSS = `
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  html,body{height:100%}
  body{background:${T.bg};font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',system-ui,sans-serif;
    color:${T.text};-webkit-font-smoothing:antialiased;font-size:14px;line-height:1.5}
  button,input,select,textarea{font-family:inherit;font-size:inherit}
  ::-webkit-scrollbar{width:5px;height:5px}
  ::-webkit-scrollbar-track{background:transparent}
  ::-webkit-scrollbar-thumb{background:#CBD5E1;border-radius:4px}
  ::-webkit-scrollbar-thumb:hover{background:#94A3B8}
  @keyframes spin{to{transform:rotate(360deg)}}
  @keyframes in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
  @keyframes blink{0%,100%{opacity:1}50%{opacity:.3}}
  @keyframes pulse-ring{0%{box-shadow:0 0 0 0 rgba(220,38,38,.4)}70%{box-shadow:0 0 0 6px rgba(220,38,38,0)}100%{box-shadow:0 0 0 0 rgba(220,38,38,0)}}
  .nav-item:hover{background:rgba(255,255,255,.08)!important;color:#fff!important}
  .row-hover:hover{background:#F8FAFC!important}
  .btn-base:hover{filter:brightness(.92)}
  .kpi-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);transform:translateY(-1px)}
  .kpi-card{transition:box-shadow .15s,transform .15s}
`;

// ─────────────────────────────────────────────────────────
// Tiny helpers
// ─────────────────────────────────────────────────────────
const fmtDate = d => !d ? "—" : new Date(d).toLocaleDateString("en-IN",{day:"numeric",month:"short",year:"numeric"});
const fmtTime = d => !d ? "—" : new Date(d).toLocaleTimeString("en-IN",{hour:"2-digit",minute:"2-digit",second:"2-digit"});
const daysSince = d => !d ? null : Math.floor((Date.now()-new Date(d))/86400000);
const waitStr  = m => m < 60 ? `${m}m` : `${Math.floor(m/60)}h ${m%60}m`;

// ─────────────────────────────────────────────────────────
// Shared primitives
// ─────────────────────────────────────────────────────────
function Spinner(){
  return(
    <div style={{display:"flex",justifyContent:"center",padding:52}}>
      <div style={{width:24,height:24,borderRadius:"50%",
        border:`2px solid ${T.border}`,borderTopColor:T.primary,
        animation:"spin .65s linear infinite"}}/>
    </div>
  );
}

function Empty({icon="—",text}){
  return(
    <div style={{padding:"48px 24px",textAlign:"center",color:T.sub}}>
      {icon && <div style={{fontSize:28,marginBottom:10,opacity:.35}}>{icon}</div>}
      <div style={{fontSize:13}}>{text}</div>
    </div>
  );
}

// Pill badge — no gradient, no glow, flat
function Pill({label,color,bg,dot=false,pulse=false}){
  return(
    <span style={{display:"inline-flex",alignItems:"center",gap:5,
      background:bg,color,padding:"2px 8px",borderRadius:4,
      fontSize:11,fontWeight:600,letterSpacing:"0.01em",whiteSpace:"nowrap"}}>
      {dot&&<span style={{width:5,height:5,borderRadius:"50%",background:color,flexShrink:0,
        animation:pulse?"blink 1.4s ease-in-out infinite":"none"}}/>}
      {label}
    </span>
  );
}

function UrgencyPill({u}){
  const m={
    urgent:  {bg:T.rLight,  color:T.red,   dot:true,pulse:true},
    normal:  {bg:T.aLight,  color:T.amber, dot:true},
    planned: {bg:T.gLight,  color:T.green, dot:true},
  }[u]??{bg:"#F3F4F6",color:T.sub};
  return <Pill label={u??"—"} {...m}/>;
}
function StatusPill({s}){
  const m={
    pending:   {bg:"#FEF3C7",color:"#92400E"},
    matched:   {bg:T.bLight, color:T.blue},
    escalated: {bg:T.rLight, color:T.red, dot:true,pulse:true},
    fulfilled: {bg:T.gLight, color:T.green},
    completed: {bg:T.gLight, color:T.green},
  }[s?.toLowerCase()]??{bg:"#F3F4F6",color:T.sub};
  return <Pill label={s??"—"} {...m}/>;
}
function BloodPill({type}){
  return(
    <span style={{background:T.rLight,color:T.red,padding:"2px 7px",
      borderRadius:3,fontWeight:700,fontSize:12,letterSpacing:"0.03em"}}>
      {type??"—"}
    </span>
  );
}

// Thin progress bar
function ScoreBar({score}){
  const pct = score>10 ? Math.min(score,100) : Math.round((score/10)*100);
  const c   = pct>=70 ? T.green : pct>=40 ? T.amber : T.red;
  return(
    <div style={{display:"flex",alignItems:"center",gap:8}}>
      <div style={{flex:1,background:"#F3F4F6",borderRadius:3,height:5,minWidth:60}}>
        <div style={{width:`${pct}%`,height:5,borderRadius:3,background:c,transition:"width .3s"}}/>
      </div>
      <span style={{fontSize:11,fontWeight:600,color:c,minWidth:26,textAlign:"right"}}>{pct}%</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Card
// ─────────────────────────────────────────────────────────
function Card({children,style}){
  return(
    <div style={{background:T.card,borderRadius:8,
      border:`1px solid ${T.border}`,overflow:"hidden",...style}}>
      {children}
    </div>
  );
}
function CardHead({title,sub,right}){
  return(
    <div style={{padding:"14px 18px",borderBottom:`1px solid ${T.border}`,
      display:"flex",alignItems:"center",justifyContent:"space-between",gap:12}}>
      <div>
        <div style={{fontWeight:600,fontSize:14,color:T.text}}>{title}</div>
        {sub&&<div style={{fontSize:12,color:T.sub,marginTop:1}}>{sub}</div>}
      </div>
      {right&&<div style={{flexShrink:0}}>{right}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Table
// ─────────────────────────────────────────────────────────
function Tbl({cols,rows,empty="No data"}){
  return(
    <div style={{overflowX:"auto"}}>
      <table style={{width:"100%",borderCollapse:"collapse",fontSize:13}}>
        <thead>
          <tr style={{background:"#F9FAFB",borderBottom:`1px solid ${T.border}`}}>
            {cols.map(c=>(
              <th key={c} style={{padding:"8px 16px",textAlign:"left",
                fontSize:10,fontWeight:700,color:T.sub,
                textTransform:"uppercase",letterSpacing:"0.07em",whiteSpace:"nowrap"}}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
      {(!rows||rows.length===0)&&<Empty text={empty}/>}
    </div>
  );
}
function Row({cells,onClick,warn}){
  const [hov,setHov]=useState(false);
  return(
    <tr onClick={onClick}
      onMouseEnter={()=>setHov(true)} onMouseLeave={()=>setHov(false)}
      style={{background:warn?"#FFFBFB":hov?"#FAFAFA":T.card,
        borderBottom:`1px solid ${T.border}`,
        cursor:onClick?"pointer":"default",transition:"background .1s"}}>
      {cells.map((c,i)=>(
        <td key={i} style={{padding:"10px 16px",
          color:c?.muted?T.sub:T.text,
          fontWeight:c?.bold?600:400,
          whiteSpace:c?.nowrap?"nowrap":undefined}}>
          {c?.v??c}
        </td>
      ))}
    </tr>
  );
}

// ─────────────────────────────────────────────────────────
// Button — solid minimal, no radius overkill
// ─────────────────────────────────────────────────────────
function Btn({label,onClick,color=T.primary,sm,disabled,ghost}){
  const [busy,setBusy]=useState(false);
  const [done,setDone]=useState("");
  async function go(e){
    e.stopPropagation();
    if(busy||disabled||done)return;
    setBusy(true);
    try{
      await onClick();
      // success flash handled by toast — just reset
    }catch(err){
      console.error(err);
      setDone("✗");
      setTimeout(()=>setDone(""),3000);
    }finally{ setBusy(false); }
  }
  const isBloodBank = typeof label==="string" && label.includes("Blood Bank");
  const busyLabel   = isBloodBank ? "Sending email…" : "…";
  return(
    <button onClick={go} disabled={busy||disabled||!!done} style={{
      padding:sm?"3px 10px":"6px 14px",
      border:ghost?`1px solid ${color}`:"none",
      borderRadius:5,
      background:ghost?"transparent":done==="✗"?T.red:(busy||disabled?"#9CA3AF":color),
      color:ghost?color:"#fff",
      fontSize:sm?11:12,fontWeight:500,
      opacity:disabled?.5:1,
      cursor:busy||disabled||done?"not-allowed":"pointer",
      transition:"opacity .1s, background .1s",
      whiteSpace:"nowrap",
      minWidth:busy&&isBloodBank?110:undefined,
    }}>{busy?busyLabel:done||label}</button>
  );
}

// ─────────────────────────────────────────────────────────
// Toast
// ─────────────────────────────────────────────────────────
function useToast(){
  const [list,setList]=useState([]);
  const add=useCallback((msg,type="ok")=>{
    const id=Date.now();
    setList(p=>[...p,{id,msg,type}]);
    setTimeout(()=>setList(p=>p.filter(t=>t.id!==id)),4200);
  },[]);
  return{list,add};
}
function Toasts({list}){
  const bg={ok:T.green,err:T.red,warn:T.amber};
  return(
    <div style={{position:"fixed",bottom:20,right:20,zIndex:9999,
      display:"flex",flexDirection:"column",gap:6}}>
      {list.map(t=>(
        <div key={t.id} style={{
          background:bg[t.type]??T.green,color:"#fff",
          padding:"9px 14px",borderRadius:6,fontSize:13,fontWeight:500,
          maxWidth:300,boxShadow:"0 2px 8px rgba(0,0,0,.15)",
          animation:"in .2s ease"}}>
          {t.msg}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Sidebar + nav
// ─────────────────────────────────────────────────────────
const NAV=[
  {id:"overview",  label:"Overview",      icon:"#"},
  {id:"requests",  label:"Requests",      icon:"\u25a6"},
  {id:"donors",    label:"Donor Pool",    icon:"\u25cf"},
  {id:"analytics", label:"Analytics",     icon:"\u2571"},
  {id:"critical",  label:"Critical Cases",icon:"!"},
  {id:"upcoming",  label:"Upcoming",      icon:"\u25f7"},
  {id:"activity",  label:"Activity Feed", icon:"\u22ef"},
];

function Sidebar({active,onNav,critCount,offline}){
  return(
    <aside style={{width:212,flexShrink:0,background:T.sidebar,
      minHeight:"100vh",display:"flex",flexDirection:"column",
      position:"sticky",top:0,height:"100vh",
      borderRight:"1px solid rgba(255,255,255,.04)"}}>

      {/* Logo */}
      <div style={{padding:"22px 18px 18px",
        borderBottom:"1px solid rgba(255,255,255,.06)"}}>
        <div style={{display:"flex",alignItems:"center",gap:10}}>
          <div style={{width:32,height:32,borderRadius:8,
            background:"linear-gradient(135deg,#DC2626,#7C3AED)",
            display:"flex",alignItems:"center",justifyContent:"center",
            fontSize:16,flexShrink:0}}>
            🩸
          </div>
          <div>
            <div style={{fontWeight:800,fontSize:15,color:"#F1F5F9",letterSpacing:"-0.3px"}}>PRAAN</div>
            <div style={{fontSize:10,color:"rgba(255,255,255,.3)",letterSpacing:"0.1em",
              textTransform:"uppercase",marginTop:1}}>Blood Warriors</div>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav style={{flex:1,padding:"8px 10px",display:"flex",flexDirection:"column",gap:1}}>
        {NAV.map(n=>{
          const act=active===n.id;
          return(
            <button key={n.id} className="nav-item" onClick={()=>onNav(n.id)} style={{
              display:"flex",alignItems:"center",justifyContent:"space-between",
              width:"100%",padding:"8px 10px",borderRadius:7,border:"none",
              background:act?"rgba(255,255,255,.12)":"transparent",
              color:act?"#F1F5F9":"rgba(255,255,255,.4)",
              fontSize:13,fontWeight:act?600:400,
              cursor:"pointer",transition:"all .12s",textAlign:"left",
              gap:10}}>
              <div style={{display:"flex",alignItems:"center",gap:9}}>
                <span style={{width:18,textAlign:"center",fontSize:13,
                  opacity:act?.9:.5,fontFamily:"monospace"}}>{n.icon}</span>
                <span>{n.label}</span>
              </div>
              {n.id==="critical"&&critCount>0&&(
                <span style={{
                  background:T.red,color:"#fff",borderRadius:20,
                  fontSize:10,fontWeight:700,padding:"1px 7px",minWidth:20,
                  textAlign:"center",animation:"blink 2s infinite"}}>
                  {critCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div style={{padding:"12px 14px 16px",borderTop:"1px solid rgba(255,255,255,.05)"}}>
        <div style={{display:"flex",alignItems:"center",gap:8,
          padding:"7px 10px",borderRadius:7,
          background:offline?"rgba(220,38,38,.12)":"rgba(16,185,129,.1)"}}>
          <span style={{width:6,height:6,borderRadius:"50%",flexShrink:0,
            background:offline?T.red:"#10B981",
            animation:offline?"none":"blink 2.5s infinite"}}/>
          <span style={{fontSize:11,color:offline?"#FCA5A5":"#6EE7B7",fontWeight:500}}>
            {offline?"Offline — demo mode":"Live data"}
          </span>
        </div>
      </div>
    </aside>
  );
}

// ─────────────────────────────────────────────────────────
// Top bar
// ─────────────────────────────────────────────────────────
const TITLES={overview:"Overview",requests:"Requests",donors:"Donor Pool",
  analytics:"Analytics",critical:"Critical Cases",
  upcoming:"Upcoming Transfusions",activity:"Activity Feed"};

function TopBar({page,countdown,loading}){
  const [now,setNow]=useState(new Date());
  useEffect(()=>{const t=setInterval(()=>setNow(new Date()),1000);return()=>clearInterval(t);},[]);
  const dateStr = now.toLocaleDateString("en-IN",{weekday:"short",day:"numeric",month:"short",year:"numeric"});
  return(
    <div style={{background:T.card,borderBottom:`1px solid ${T.border}`,
      padding:"12px 24px",display:"flex",alignItems:"center",
      justifyContent:"space-between",position:"sticky",top:0,zIndex:100,
      boxShadow:"0 1px 0 rgba(0,0,0,.04)"}}>
      <div>
        <span style={{fontWeight:700,fontSize:16,color:T.text,letterSpacing:"-0.2px"}}>{TITLES[page]}</span>
        <span style={{fontSize:12,color:T.faint,marginLeft:10}}>{dateStr}</span>
      </div>
      <div style={{display:"flex",alignItems:"center",gap:10}}>
        {loading&&(
          <div style={{display:"flex",alignItems:"center",gap:6,
            fontSize:12,color:T.primary}}>
            <div style={{width:12,height:12,borderRadius:"50%",
              border:`1.5px solid ${T.primary}40`,borderTopColor:T.primary,
              animation:"spin .6s linear infinite"}}/>
            Refreshing
          </div>
        )}
        {!loading&&(
          <span style={{fontSize:12,color:T.faint}}>Refresh in {countdown}s</span>
        )}
        <div style={{width:1,height:16,background:T.border}}/>
        <span style={{fontSize:12,fontWeight:600,color:T.sub,
          background:"#F1F5F9",padding:"4px 10px",borderRadius:6,
          fontVariantNumeric:"tabular-nums",letterSpacing:"0.02em"}}>
          {fmtTime(now)}
        </span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// KPI card — bold number, icon, trend label
// ─────────────────────────────────────────────────────────
const KPI_META = {
  active_requests:    { icon: "🩸", trend: "Active" },
  donors_notified:    { icon: "📣", trend: "Notified" },
  confirmed_today:    { icon: "✓",  trend: "Today" },
  critical_cases:     { icon: "⚡", trend: "Critical" },
  patients_due_7days: { icon: "📅", trend: "In 7 days" },
  avg_match_time:     { icon: "⏱",  trend: "Avg time" },
};

function KPI({label,val,color,pulse,metaKey}){
  const meta = KPI_META[metaKey] || {};
  return(
    <div className="kpi-card" style={{
      background:T.card,
      borderRadius:10,
      border:`1px solid ${T.border}`,
      padding:"18px 20px",
      display:"flex",flexDirection:"column",gap:12,
      position:"relative",overflow:"hidden",
    }}>
      {/* accent strip */}
      <div style={{position:"absolute",top:0,left:0,right:0,height:3,background:color,borderRadius:"10px 10px 0 0"}}/>
      <div style={{display:"flex",alignItems:"center",justifyContent:"space-between"}}>
        <span style={{fontSize:12,color:T.sub,fontWeight:500,letterSpacing:"0.01em"}}>{label}</span>
        <span style={{fontSize:18,lineHeight:1,opacity:.7}}>{meta.icon}</span>
      </div>
      <div style={{
        fontSize:32,fontWeight:800,color,lineHeight:1,
        letterSpacing:"-1px",
        animation:pulse?"blink 2s infinite":"none"
      }}>
        {val??<span style={{color:T.faint,fontSize:20}}>—</span>}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// Chart tooltip (shared style)
// ─────────────────────────────────────────────────────────
const TTP={contentStyle:{background:T.card,border:`1px solid ${T.border}`,
  borderRadius:5,fontSize:12,padding:"6px 10px"},
  cursor:{fill:"#F3F4F6"}};

// ─────────────────────────────────────────────────────────
// PAGE — OVERVIEW
// ─────────────────────────────────────────────────────────
function OverviewPage({stats,requests,donors,critical,onAction,onView}){
  const statusCounts=[
    {name:"Pending",  v:requests.filter(r=>r.status==="pending").length,   fill:T.amber},
    {name:"Matched",  v:requests.filter(r=>r.status==="matched").length,   fill:T.blue},
    {name:"Escalated",v:requests.filter(r=>r.status==="escalated").length, fill:T.red},
    {name:"Fulfilled",v:requests.filter(r=>r.status==="fulfilled"||r.status==="completed").length, fill:T.green},
  ];

  const cityMap={};
  donors.forEach(d=>{if(d.city)cityMap[d.city]=(cityMap[d.city]||0)+(d.is_active!==false?1:0);});
  const cityData=Object.entries(cityMap)
    .map(([city,count])=>({city:city.length>6?city.slice(0,5)+"…":city,count}))
    .sort((a,b)=>b.count-a.count).slice(0,8);

  const urgent=requests.filter(r=>r.urgency==="urgent"&&r.status!=="fulfilled"&&r.status!=="completed");
  const pending=requests.filter(r=>r.status==="pending");
  const needsAction=[...new Map([...urgent,...pending].map(r=>[r.id,r])).values()].slice(0,10);

  return(
    <div style={{animation:"in .2s ease"}}>
      {/* KPIs */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(6,1fr)",gap:12,marginBottom:20}}>
        <KPI label="Active Requests"   val={stats?.active_requests}    color={T.red}     pulse={stats?.active_requests>0}   metaKey="active_requests"/>
        <KPI label="Donors Notified"   val={stats?.donors_notified}    color={T.primary}                                     metaKey="donors_notified"/>
        <KPI label="Confirmed Today"   val={stats?.confirmed_today}    color={T.green}                                       metaKey="confirmed_today"/>
        <KPI label="Critical"          val={stats?.critical_cases}     color={T.red}     pulse={stats?.critical_cases>0}    metaKey="critical_cases"/>
        <KPI label="Due in 7 Days"     val={stats?.patients_due_7days} color={T.amber}                                       metaKey="patients_due_7days"/>
        <KPI label="Avg Match Time"    val={stats?.avg_match_time}     color={T.purple}                                      metaKey="avg_match_time"/>
      </div>

      {/* Charts */}
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14,marginBottom:20}}>
        <Card>
          <CardHead title="Request Status" sub="Live count by status"/>
          <div style={{padding:"16px 8px 12px"}}>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={statusCounts} barCategoryGap="45%" barSize={32}>
                <XAxis dataKey="name" tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false}/>
                <YAxis tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false} width={24} allowDecimals={false}/>
                <Tooltip contentStyle={{background:T.card,border:`1px solid ${T.border}`,borderRadius:6,fontSize:12}} cursor={{fill:"#F1F5F9"}}/>
                <Bar dataKey="v" radius={[5,5,0,0]} name="Count">
                  {statusCounts.map((e,i)=><Cell key={i} fill={e.fill}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHead title="Active Donors by City" sub="Currently active donors"/>
          <div style={{padding:"16px 8px 12px"}}>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={cityData} barCategoryGap="40%" barSize={14} layout="vertical">
                <XAxis type="number" tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false} allowDecimals={false}/>
                <YAxis type="category" dataKey="city" tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false} width={50}/>
                <Tooltip contentStyle={{background:T.card,border:`1px solid ${T.border}`,borderRadius:6,fontSize:12}} cursor={{fill:"#F1F5F9"}}/>
                <Bar dataKey="count" fill={T.primary} radius={[0,5,5,0]} name="Donors"/>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Attention table */}
      <Card>
        <CardHead title="Needs Attention"
          sub={`${needsAction.length} request${needsAction.length!==1?"s":""} need review`}/>
        {needsAction.length===0
          ? <Empty icon="✓" text="No requests need immediate attention"/>
          : <Tbl
              cols={["Patient","Blood","City","Urgency","Waiting","Status","Actions"]}
              rows={needsAction.map(req=>{
                const mins=Math.floor((Date.now()-new Date(req.created_at))/60000);
                const late=req.urgency==="urgent"&&mins>60;
                return(
                  <Row key={req.id} warn={late}
                    onClick={()=>onView(req)}
                    cells={[
                      {v:<span style={{fontWeight:600}}>{req.patient?.name??"—"}</span>},
                      {v:<BloodPill type={req.patient?.blood_type}/>},
                      {v:req.patient?.city??"—",muted:true},
                      {v:<UrgencyPill u={req.urgency}/>},
                      {v:<span style={{color:late?T.red:T.sub,fontWeight:late?600:400,fontSize:12}}>{waitStr(mins)}</span>,nowrap:true},
                      {v:<StatusPill s={req.status}/>},
                      {v:(
                        <div style={{display:"flex",gap:5}} onClick={e=>e.stopPropagation()}>
                          {req.status==="pending"&&<Btn sm label="Find donors" onClick={()=>onAction("match",req)}/>}
                          {req.status==="matched"&&<Btn sm label="Notify" color={T.blue} onClick={()=>onAction("notify",req)}/>}
                          {(req.status==="pending"||req.status==="matched")&&
                            <Btn sm label="Escalate" color={T.red} ghost onClick={()=>onAction("escalate",req)}/>}
                        </div>
                      )},
                    ]}
                  />
                );
              })}
            />
        }
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// PAGE — REQUESTS
// ─────────────────────────────────────────────────────────
function RequestsPage({requests,loading,onAction,onView}){
  const [q,setQ]=useState("");
  const [fB,setFB]=useState("");
  const [fC,setFC]=useState("");
  const [fU,setFU]=useState("");
  const [fS,setFS]=useState("");

  const list=requests.filter(r=>{
    const str=`${r.patient?.name} ${r.patient?.city} ${r.patient?.blood_type}`.toLowerCase();
    if(q&&!str.includes(q.toLowerCase()))return false;
    if(fB&&r.patient?.blood_type!==fB)return false;
    if(fC&&r.patient?.city!==fC)return false;
    if(fU&&r.urgency!==fU)return false;
    if(fS&&r.status!==fS)return false;
    return true;
  });

  const cities=[...new Set(requests.map(r=>r.patient?.city).filter(Boolean))];
  const bloods=[...new Set(requests.map(r=>r.patient?.blood_type).filter(Boolean))];
  const sel={padding:"5px 8px",borderRadius:5,border:`1px solid ${T.border}`,
    fontSize:12,background:T.card,color:T.text,outline:"none"};

  return(
    <div style={{animation:"in .2s ease"}}>
      <Card>
        <CardHead title="All Requests" sub={`${list.length} of ${requests.length}`}
          right={
            <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
              <input value={q} onChange={e=>setQ(e.target.value)}
                placeholder="Search…" style={{...sel,width:160}}/>
              <select value={fB} onChange={e=>setFB(e.target.value)} style={sel}>
                <option value="">Blood</option>
                {bloods.map(b=><option key={b}>{b}</option>)}
              </select>
              <select value={fC} onChange={e=>setFC(e.target.value)} style={sel}>
                <option value="">City</option>
                {cities.map(c=><option key={c}>{c}</option>)}
              </select>
              <select value={fU} onChange={e=>setFU(e.target.value)} style={sel}>
                <option value="">Urgency</option>
                <option value="urgent">Urgent</option>
                <option value="normal">Normal</option>
                <option value="planned">Planned</option>
              </select>
              <select value={fS} onChange={e=>setFS(e.target.value)} style={sel}>
                <option value="">Status</option>
                <option value="pending">Pending</option>
                <option value="matched">Matched</option>
                <option value="escalated">Escalated</option>
                <option value="fulfilled">Fulfilled</option>
              </select>
            </div>
          }/>
        {loading?<Spinner/>:
          <Tbl cols={["Patient","Blood","City","Urgency","Created","Need By","Status","Source","Actions"]}
            rows={list.map(req=>(
              <Row key={req.id} onClick={()=>onView(req)}
                cells={[
                  {v:<span style={{fontWeight:600}}>{req.patient?.name??"—"}</span>},
                  {v:<BloodPill type={req.patient?.blood_type}/>},
                  {v:req.patient?.city??"—",muted:true},
                  {v:<UrgencyPill u={req.urgency}/>},
                  {v:fmtDate(req.created_at),muted:true,nowrap:true},
                  {v:fmtDate(req.predicted_date),muted:true,nowrap:true},
                  {v:<StatusPill s={req.status}/>},
                  {v:<span style={{fontSize:11,color:T.sub}}>{req.raised_by??"coordinator"}</span>},
                  {v:(
                    <div style={{display:"flex",gap:5}} onClick={e=>e.stopPropagation()}>
                      {req.status==="pending"&&<Btn sm label="Find donors" onClick={()=>onAction("match",req)}/>}
                      {req.status==="matched"&&<Btn sm label="Notify" color={T.blue} onClick={()=>onAction("notify",req)}/>}
                      {(req.status==="pending"||req.status==="matched")&&
                        <Btn sm label="Escalate" color={T.red} ghost onClick={()=>onAction("escalate",req)}/>}
                    </div>
                  )},
                ]}
              />
            ))}
          />
        }
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// PAGE — DONORS
// ─────────────────────────────────────────────────────────
function DonorsPage({donors}){
  const [q,setQ]=useState("");
  const [fB,setFB]=useState("");
  const [fC,setFC]=useState("");

  const list=donors.filter(d=>{
    const str=`${d.name} ${d.city} ${d.blood_type}`.toLowerCase();
    if(q&&!str.includes(q.toLowerCase()))return false;
    if(fB&&d.blood_type!==fB)return false;
    if(fC&&d.city!==fC)return false;
    return true;
  });

  const cities=[...new Set(donors.map(d=>d.city).filter(Boolean))];
  const bloods=[...new Set(donors.map(d=>d.blood_type).filter(Boolean))];
  const eligCount=donors.filter(d=>{const ds=daysSince(d.last_donation);return ds===null||ds>90;}).length;
  const sel={padding:"5px 8px",borderRadius:5,border:`1px solid ${T.border}`,
    fontSize:12,background:T.card,color:T.text,outline:"none"};

  return(
    <div style={{animation:"in .2s ease"}}>
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:12,marginBottom:16}}>
        <KPI label="Total Donors"   val={donors.length}                                    color={T.primary}/>
        <KPI label="Active"         val={donors.filter(d=>d.is_active!==false).length}     color={T.green}/>
        <KPI label="Eligible Now"   val={eligCount}                                        color={T.blue}/>
        <KPI label="Cooling Off"    val={donors.length-eligCount}                          color={T.amber}/>
      </div>
      <Card>
        <CardHead title="Donor Pool" sub={`${list.length} of ${donors.length}`}
          right={
            <div style={{display:"flex",gap:6}}>
              <input value={q} onChange={e=>setQ(e.target.value)}
                placeholder="Search…" style={{...sel,width:160}}/>
              <select value={fB} onChange={e=>setFB(e.target.value)} style={sel}>
                <option value="">Blood</option>
                {bloods.map(b=><option key={b}>{b}</option>)}
              </select>
              <select value={fC} onChange={e=>setFC(e.target.value)} style={sel}>
                <option value="">City</option>
                {cities.map(c=><option key={c}>{c}</option>)}
              </select>
            </div>
          }/>
        <Tbl cols={["Name","Blood","City","Reliability","Last Donation","Lang","Eligible","Active"]}
          rows={list.map((d,i)=>{
            const ds=daysSince(d.last_donation);
            const elig=ds===null||ds>90;
            return(
              <Row key={d.id??i}
                cells={[
                  {v:<span style={{fontWeight:600}}>{d.name}</span>},
                  {v:<BloodPill type={d.blood_type}/>},
                  {v:d.city,muted:true},
                  {v:<div style={{minWidth:100}}><ScoreBar score={d.response_score??5}/></div>},
                  {v:fmtDate(d.last_donation),muted:true,nowrap:true},
                  {v:<span style={{fontSize:11,color:T.sub}}>{(d.preferred_language??"en").toUpperCase()}</span>},
                  {v:<Pill label={elig?"Eligible":"Cooling off"}
                      bg={elig?T.gLight:T.aLight} color={elig?T.green:T.amber}/>},
                  {v:<span style={{width:7,height:7,borderRadius:"50%",display:"inline-block",
                    background:d.is_active!==false?T.green:"#D1D5DB"}}/>},
                ]}
              />
            );
          })}
        />
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// PAGE — ANALYTICS
// ─────────────────────────────────────────────────────────
function DonutWithLegend({data,height=200}){
  return(
    <div style={{display:"flex",alignItems:"center",gap:8,padding:"12px 16px 16px"}}>
      <ResponsiveContainer width="50%" height={height}>
        <PieChart>
          <Pie data={data} cx="50%" cy="50%"
            innerRadius={height*.28} outerRadius={height*.42}
            dataKey="v" nameKey="n" paddingAngle={2}>
            {data.map((_,i)=><Cell key={i} fill={CHART[i%CHART.length]}/>)}
          </Pie>
          <Tooltip contentStyle={{background:T.card,border:`1px solid ${T.border}`,borderRadius:6,fontSize:12}}
            formatter={(v,_,p)=>[v,p.payload.n]}/>
        </PieChart>
      </ResponsiveContainer>
      <div style={{flex:1,display:"flex",flexDirection:"column",gap:7}}>
        {data.map((d,i)=>(
          <div key={d.n} style={{display:"flex",alignItems:"center",gap:8}}>
            <span style={{width:8,height:8,borderRadius:2,flexShrink:0,
              background:CHART[i%CHART.length]}}/>
            <span style={{fontSize:12,color:T.sub,flex:1,lineHeight:1.3}}>{d.n}</span>
            <span style={{fontSize:13,fontWeight:700,color:T.text}}>{d.v}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AnalyticsPage({requests,donors}){
  // Patient blood type
  const ptMap={};
  requests.forEach(r=>{const b=r.patient?.blood_type;if(b)ptMap[b]=(ptMap[b]||0)+1;});
  const ptData=Object.entries(ptMap).map(([n,v])=>({n,v}));

  // Donor blood type
  const dtMap={};
  donors.forEach(d=>{if(d.blood_type)dtMap[d.blood_type]=(dtMap[d.blood_type]||0)+1;});
  const dtData=Object.entries(dtMap).map(([n,v])=>({n,v}));

  // Reliability histogram
  const buckets=[
    {r:"0–20",c:0},{r:"21–40",c:0},{r:"41–60",c:0},{r:"61–80",c:0},{r:"81–100",c:0}
  ];
  donors.forEach(d=>{
    const p=d.response_score>10?Math.min(d.response_score,100):Math.round((d.response_score/10)*100);
    if(p<=20)buckets[0].c++;
    else if(p<=40)buckets[1].c++;
    else if(p<=60)buckets[2].c++;
    else if(p<=80)buckets[3].c++;
    else buckets[4].c++;
  });

  // City coverage
  const cities=[...new Set([...requests.map(r=>r.patient?.city),...donors.map(d=>d.city)].filter(Boolean))];
  const coverage=cities.map(city=>({
    city:city.length>7?city.slice(0,6)+"…":city,
    donors:donors.filter(d=>d.city===city&&d.is_active!==false).length,
    requests:requests.filter(r=>r.patient?.city===city&&r.status!=="fulfilled"&&r.status!=="completed").length,
  }));

  // Eligibility
  const eligCount=donors.filter(d=>{const ds=daysSince(d.last_donation);return ds===null||ds>90;}).length;
  const eligData=[{n:"Eligible",v:eligCount},{n:"Cooling off",v:donors.length-eligCount}];

  return(
    <div style={{animation:"in .2s ease",display:"flex",flexDirection:"column",gap:14}}>
      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <Card>
          <CardHead title="Patient Blood Types" sub="Demand distribution"/>
          <DonutWithLegend data={ptData}/>
        </Card>
        <Card>
          <CardHead title="Donor Blood Types" sub="Supply distribution"/>
          <DonutWithLegend data={dtData}/>
        </Card>
      </div>

      <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:14}}>
        <Card>
          <CardHead title="Donor Reliability" sub="Response score distribution"/>
          <div style={{padding:"12px 8px 12px"}}>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={buckets} barCategoryGap="40%" barSize={28}>
                <XAxis dataKey="r" tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false}/>
                <YAxis tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false} width={24} allowDecimals={false}/>
                <Tooltip contentStyle={{background:T.card,border:`1px solid ${T.border}`,borderRadius:6,fontSize:12}} cursor={{fill:"#F1F5F9"}}/>
                <Bar dataKey="c" radius={[5,5,0,0]} name="Donors">
                  {buckets.map((_,i)=><Cell key={i} fill={CHART[i%CHART.length]}/>)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card>
          <CardHead title="Donor Eligibility" sub="90-day cooling period"/>
          <DonutWithLegend data={eligData} height={180}/>
        </Card>
      </div>

      <Card>
        <CardHead title="City Coverage" sub="Active donors vs open requests"/>
        <div style={{padding:"12px 8px 12px"}}>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={coverage} barCategoryGap="35%">
              <XAxis dataKey="city" tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false}/>
              <YAxis tick={{fontSize:11,fill:T.sub}} axisLine={false} tickLine={false} width={24} allowDecimals={false}/>
              <Tooltip contentStyle={{background:T.card,border:`1px solid ${T.border}`,borderRadius:6,fontSize:12}} cursor={{fill:"#F1F5F9"}}/>
              <Legend wrapperStyle={{fontSize:11,paddingTop:8}}/>
              <Bar dataKey="donors"   fill={T.primary} radius={[5,5,0,0]} name="Active Donors"/>
              <Bar dataKey="requests" fill={T.red}     radius={[5,5,0,0]} name="Open Requests"/>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// PAGE — CRITICAL
// ─────────────────────────────────────────────────────────
function CriticalPage({critical,loading,onAction}){
  return(
    <div style={{animation:"in .2s ease"}}>
      {critical.length>0&&(
        <div style={{background:T.rLight,border:`1px solid ${T.rBorder}`,
          borderRadius:6,padding:"10px 16px",marginBottom:14,
          display:"flex",alignItems:"center",gap:10}}>
          <span style={{color:T.red,fontSize:13,fontWeight:600}}>
            {critical.length} case{critical.length!==1?"s":""} require immediate intervention —
            no donor confirmed
          </span>
        </div>
      )}
      <Card>
        <CardHead title="Critical Cases" sub="Requests with no confirmed donor"/>
        {loading?<Spinner/>:critical.length===0
          ?<Empty icon="✓" text="No critical cases right now"/>
          :<Tbl cols={["Patient","Blood","City","Waiting","Reason","Stage","Actions"]}
              rows={critical.map(c=>(
                <Row key={c.id} warn={c.waiting_minutes>=90}
                  cells={[
                    {v:<span style={{fontWeight:600}}>{c.patient}</span>},
                    {v:<BloodPill type={c.blood_type}/>},
                    {v:c.city,muted:true},
                    {v:(
                      <span style={{fontWeight:700,fontSize:12,
                        color:c.waiting_minutes>=90?T.red:c.waiting_minutes>=60?T.amber:T.sub,
                        animation:c.waiting_minutes>=90?"blink 1.5s infinite":"none"}}>
                        {waitStr(c.waiting_minutes)}
                      </span>
                    ),nowrap:true},
                    {v:c.reason,muted:true},
                    {v:<StatusPill s={c.current_stage}/>},
                    {v:(
                      <div style={{display:"flex",gap:5}}>
                        <Btn sm label="Notify more" color={T.blue}
                          onClick={()=>onAction("match",{id:c.id,status:"pending",patient:{name:c.patient}})}/>
                        <Btn sm label="Escalate" color={T.red}
                          onClick={()=>onAction("escalate",{id:c.id,patient:{name:c.patient}})}/>
                        <Btn sm label="📧 Blood Bank" color={T.primary}
                          onClick={()=>onAction("bloodbank",{id:c.id,patient:{name:c.patient}})}/>
                      </div>
                    )},
                  ]}
                />
              ))}
            />
        }
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// PAGE — UPCOMING
// ─────────────────────────────────────────────────────────
function UpcomingPage({predictions,loading,onRun}){
  return(
    <div style={{animation:"in .2s ease"}}>
      <Card>
        <CardHead title="Upcoming Transfusions"
          sub="AI-predicted patients who will need blood soon"
          right={<Btn label="Run predictions" onClick={onRun}/>}/>
        {loading?<Spinner/>:predictions.length===0
          ?<Empty icon="◷" text='Click "Run predictions" to forecast upcoming transfusion needs.'/>
          :(
            <>
              <div style={{padding:"14px 6px 4px"}}>
                <ResponsiveContainer width="100%" height={140}>
                  <BarChart
                    data={predictions.slice(0,12).map(r=>({
                      n:r.patient_name.split(" ")[0],
                      days:r.days_until_needed,
                      fill:r.days_until_needed<=2?T.red:r.days_until_needed<=5?T.amber:T.green,
                    }))}
                    barCategoryGap="25%">
                    <XAxis dataKey="n" tick={{fontSize:10,fill:T.sub}} axisLine={false} tickLine={false}/>
                    <YAxis tick={{fontSize:10,fill:T.sub}} axisLine={false} tickLine={false} width={20}/>
                    <Tooltip {...TTP} formatter={v=>[`${v} days`,"Until needed"]}/>
                    <Bar dataKey="days" radius={[3,3,0,0]} name="Days">
                      {predictions.slice(0,12).map((r,i)=>(
                        <Cell key={i}
                          fill={r.days_until_needed<=2?T.red:r.days_until_needed<=5?T.amber:T.green}/>
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <Tbl cols={["Patient","Date","Days","Priority","Confidence","Notes"]}
                rows={predictions.map((r,i)=>{
                  const d=r.days_until_needed;
                  const pc=d<=2?T.red:d<=5?T.amber:T.green;
                  const pb=d<=2?T.rLight:d<=5?T.aLight:T.gLight;
                  return(
                    <Row key={r.patient_id??i}
                      cells={[
                        {v:<span style={{fontWeight:600}}>{r.patient_name}</span>},
                        {v:fmtDate(r.predicted_date),muted:true,nowrap:true},
                        {v:<span style={{fontWeight:700,color:pc}}>{d<=0?"Today":`${d}d`}</span>},
                        {v:<Pill label={d<=2?"High":d<=5?"Medium":"Low"} bg={pb} color={pc}/>},
                        {v:<div style={{minWidth:90}}><ScoreBar score={Math.round(r.confidence*100)}/></div>},
                        {v:r.reasoning,muted:true},
                      ]}
                    />
                  );
                })}
              />
            </>
          )
        }
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// PAGE — ACTIVITY FEED
// ─────────────────────────────────────────────────────────
function ActivityPage({feed,loading,onRefresh}){
  const [filter,setFilter]=useState("all");
  const list=filter==="all"?feed:feed.filter(e=>e.type===filter);
  const typeColor={info:T.green,warn:T.amber,alert:T.red,error:T.red};

  return(
    <div style={{animation:"in .2s ease"}}>
      <Card>
        <CardHead title="Activity Feed" sub={`${list.length} events`}
          right={
            <div style={{display:"flex",gap:6,alignItems:"center"}}>
              {["all","info","warn","alert"].map(t=>(
                <button key={t} onClick={()=>setFilter(t)} style={{
                  padding:"3px 9px",borderRadius:4,border:"none",
                  background:filter===t?T.primary:"#F3F4F6",
                  color:filter===t?"#fff":T.sub,
                  fontSize:11,fontWeight:500,cursor:"pointer"}}>
                  {t==="all"?"All":t.charAt(0).toUpperCase()+t.slice(1)}
                </button>
              ))}
              <Btn sm label="↻ Refresh" onClick={onRefresh}/>
            </div>
          }/>
        {loading?<Spinner/>:list.length===0
          ?<Empty text="No activity yet. Events appear here as requests are processed."/>
          :(
            <div>
              {list.map((e,i)=>{
                const color=typeColor[e.type]??T.sub;
                return(
                  <div key={i} style={{
                    display:"flex",alignItems:"flex-start",gap:12,
                    padding:"9px 18px",
                    borderBottom:i<list.length-1?`1px solid ${T.border}`:"none",
                    background:e.type==="alert"?"#FFFBFB":"transparent"}}>
                    <span style={{fontSize:11,color:T.faint,minWidth:68,
                      paddingTop:1,flexShrink:0,fontVariantNumeric:"tabular-nums"}}>
                      {fmtTime(e.ts)}
                    </span>
                    <span style={{background:color+"18",color,
                      padding:"1px 7px",borderRadius:3,fontSize:10,
                      fontWeight:700,flexShrink:0,marginTop:2,
                      textTransform:"uppercase"}}>
                      {e.type??"info"}
                    </span>
                    <span style={{fontSize:13,color:e.type==="alert"?T.red:T.text,
                      fontWeight:e.type==="alert"?500:400,lineHeight:1.5}}>
                      {e.msg}
                    </span>
                  </div>
                );
              })}
            </div>
          )
        }
      </Card>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// REQUEST DETAIL MODAL — bug fixed: refetch after action
// ─────────────────────────────────────────────────────────
function DetailModal({req,onClose,onAction,add}){
  const [detail,setDetail]=useState(null);
  const [loading,setLoading]=useState(true);
  const [refetch,setRefetch]=useState(0);

  useEffect(()=>{
    if(!req?.id) return;
    setLoading(true);
    axios.get(`${API}/requests/${req.id}`,{timeout:7000})
      .then(r=>setDetail(r.data))
      .catch(()=>setDetail({...req,matches:[]}))
      .finally(()=>setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[req.id,refetch]);

  // action from inside modal — refetch after so donors appear
  async function act(type){
    try{
      if(type==="match")    await axios.post(`${API}/requests/${req.id}/match`,{},{timeout:10000});
      if(type==="notify")   await axios.post(`${API}/notify/${req.id}`,{},{timeout:8000});
      if(type==="escalate") await axios.post(`${API}/requests/${req.id}/escalate`,{},{timeout:8000});
      add(`Done — ${type}`, "ok");
      setRefetch(n=>n+1); // triggers re-fetch of detail with fresh matches
    }catch(err){ add(`Failed: ${err.message}`,"err"); }
  }

  return(
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,.38)",
      zIndex:1000,display:"flex",alignItems:"center",justifyContent:"center",
      padding:24}} onClick={onClose}>
      <div style={{background:T.card,borderRadius:8,width:"100%",maxWidth:720,
        maxHeight:"88vh",overflowY:"auto",animation:"in .18s ease",
        border:`1px solid ${T.border}`}}
        onClick={e=>e.stopPropagation()}>

        {/* header */}
        <div style={{padding:"14px 20px",borderBottom:`1px solid ${T.border}`,
          display:"flex",alignItems:"center",justifyContent:"space-between"}}>
          <span style={{fontWeight:600,fontSize:14}}>Request Details</span>
          <button onClick={onClose} style={{background:"none",border:"none",
            fontSize:18,color:T.sub,cursor:"pointer",lineHeight:1}}>×</button>
        </div>

        {loading?<Spinner/>:detail&&(
          <div style={{padding:20}}>
            {/* patient grid */}
            <div style={{display:"grid",gridTemplateColumns:"repeat(3,1fr)",gap:8,marginBottom:20}}>
              {[
                {l:"Name",      v:detail.patient?.name},
                {l:"Blood",     v:detail.patient?.blood_type},
                {l:"City",      v:detail.patient?.city},
                {l:"Urgency",   v:detail.urgency},
                {l:"Need by",   v:fmtDate(detail.predicted_date)},
                {l:"Status",    v:detail.status},
              ].map(f=>(
                <div key={f.l} style={{background:"#F9FAFB",borderRadius:6,padding:"9px 12px",
                  border:`1px solid ${T.border}`}}>
                  <div style={{fontSize:10,color:T.sub,fontWeight:600,
                    textTransform:"uppercase",letterSpacing:"0.06em",marginBottom:3}}>{f.l}</div>
                  <div style={{fontSize:13,fontWeight:600}}>{f.v??"—"}</div>
                </div>
              ))}
            </div>

            {/* matched donors */}
            <div style={{fontSize:11,fontWeight:700,color:T.sub,textTransform:"uppercase",
              letterSpacing:"0.07em",marginBottom:10}}>
              Matched Donors
            </div>
            {!detail.matches?.length?(
              <div style={{color:T.sub,fontSize:13,marginBottom:16,padding:"12px 0"}}>
                No donors matched yet.
                {detail.status==="pending"&&(
                  <span style={{marginLeft:8}}>
                    <Btn sm label="Find donors now" onClick={()=>act("match")}/>
                  </span>
                )}
              </div>
            ):detail.matches.map((m,i)=>{
              const d=m.donor;
              return(
                <div key={m.id??i} style={{border:`1px solid ${T.border}`,
                  borderLeft:`3px solid ${i===0?T.primary:T.border}`,
                  borderRadius:6,padding:"11px 14px",marginBottom:8}}>
                  <div style={{display:"flex",justifyContent:"space-between",
                    alignItems:"center",marginBottom:m.reasons?.length?8:0}}>
                    <div style={{display:"flex",alignItems:"center",gap:8}}>
                      <span style={{background:i===0?T.primary:"#6B7280",color:"#fff",
                        borderRadius:3,fontSize:10,fontWeight:700,padding:"1px 6px"}}>
                        {i===0?"Primary":`Backup ${i}`}
                      </span>
                      <span style={{fontWeight:600,fontSize:13}}>{d?.name??"—"}</span>
                      <BloodPill type={d?.blood_type}/>
                      {d?.city&&<span style={{fontSize:11,color:T.sub}}>{d.city}</span>}
                    </div>
                    <Pill
                      label={m.confirmed?"Confirmed ✓":"Pending"}
                      bg={m.confirmed?T.gLight:"#F3F4F6"}
                      color={m.confirmed?T.green:T.sub}/>
                  </div>
                  {m.reasons?.length>0&&(
                    <div style={{display:"flex",gap:6,flexWrap:"wrap"}}>
                      {m.reasons.map((r,ri)=>(
                        <span key={ri} style={{background:T.gLight,color:T.green,
                          fontSize:11,padding:"1px 7px",borderRadius:3,fontWeight:500}}>
                          {r}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}

            {/* actions */}
            <div style={{borderTop:`1px solid ${T.border}`,paddingTop:14,
              display:"flex",gap:8,flexWrap:"wrap",marginTop:4}}>
              {(detail.status==="pending")&&
                <Btn label="Find donors" onClick={()=>act("match")}/>}
              {detail.status==="matched"&&
                <Btn label="Notify more" color={T.blue} onClick={()=>act("notify")}/>}
              <Btn label="Escalate" color={T.red} onClick={()=>act("escalate")}/>
              <Btn label="Close" color={T.sub} ghost onClick={onClose}/>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────
// ROOT
// ─────────────────────────────────────────────────────────
export default function App(){
  const [page,setPage]               = useState("overview");
  const [stats,setStats]             = useState(null);
  const [requests,setRequests]       = useState([]);
  const [donors,setDonors]           = useState([]);
  const [critical,setCritical]       = useState([]);
  const [feed,setFeed]               = useState([]);
  const [predictions,setPredictions] = useState([]);
  const [ldReqs,setLdReqs]           = useState(false);
  const [ldCrit,setLdCrit]           = useState(false);
  const [ldFeed,setLdFeed]           = useState(false);
  const [ldPred,setLdPred]           = useState(false);
  const [offline,setOffline]         = useState(false);
  const [countdown,setCountdown]     = useState(POLL);
  const [modal,setModal]             = useState(null);
  const countRef                     = useRef(POLL);
  const {list:toasts,add}            = useToast();

  useEffect(()=>{
    const el=document.createElement("style");
    el.textContent=CSS;
    document.head.appendChild(el);
    return()=>document.head.removeChild(el);
  },[]);

  // ── fetchers ──────────────────────────────────────────
  const fetchStats = useCallback(async()=>{
    try{ const{data}=await axios.get(`${API}/stats`,{timeout:4000}); setStats(data); setOffline(false); }
    catch{ setOffline(true); }
  },[]);

  const fetchReqs = useCallback(async()=>{
    setLdReqs(true);
    try{ const{data}=await axios.get(`${API}/requests`,{timeout:4000}); setRequests(data); }
    catch{}finally{ setLdReqs(false); }
  },[]);

  const fetchDonors = useCallback(async()=>{
    try{ const{data}=await axios.get(`${API}/donors`,{timeout:4000}); setDonors(data); }catch{}
  },[]);

  const fetchCrit = useCallback(async()=>{
    setLdCrit(true);
    try{ const{data}=await axios.get(`${API}/critical`,{timeout:4000}); setCritical(data); }
    catch{}finally{ setLdCrit(false); }
  },[]);

  const fetchFeed = useCallback(async()=>{
    setLdFeed(true);
    try{ const{data}=await axios.get(`${API}/activity?limit=100`,{timeout:4000}); setFeed(data); }
    catch{}finally{ setLdFeed(false); }
  },[]);

  const runPred = useCallback(async()=>{
    setLdPred(true);
    try{
      const{data}=await axios.post(`${API}/predict/bulk`,{},{timeout:12000});
      setPredictions(data);
      add(`Predictions ready for ${data.length} patients`,"ok");
    }catch{ add("Prediction failed","err"); }
    finally{ setLdPred(false); }
  },[add]);

  // ── central action handler ────────────────────────────
  const doAction = useCallback(async(type,req)=>{
    try{
      if(type==="match")     await axios.post(`${API}/requests/${req.id}/match`,{},{timeout:10000});
      if(type==="notify")    await axios.post(`${API}/notify/${req.id}`,{},{timeout:8000});
      if(type==="escalate")  await axios.post(`${API}/requests/${req.id}/escalate`,{},{timeout:8000});
      if(type==="bloodbank") await axios.post(`${API}/requests/${req.id}/contact-blood-bank`,{},{timeout:60000});
      const msg={match:"Donors matched",notify:"Notification sent",escalate:"Escalated",bloodbank:"✓ Email sent to blood bank"}[type];
      add(`${msg} — ${req.patient?.name??"request"}`, type==="escalate"?"warn":"ok");
      await Promise.all([fetchReqs(),fetchStats(),fetchCrit(),fetchFeed()]);
    }catch(err){ add(`Action failed: ${err.message}`,"err"); }
  },[fetchReqs,fetchStats,fetchCrit,fetchFeed,add]);

  // ── bootstrap ─────────────────────────────────────────
  useEffect(()=>{
    fetchStats(); fetchReqs(); fetchDonors(); fetchCrit(); fetchFeed();
  },[fetchStats,fetchReqs,fetchDonors,fetchCrit,fetchFeed]);

  // ── auto-refresh ──────────────────────────────────────
  useEffect(()=>{
    countRef.current=POLL; setCountdown(POLL);
    const t=setInterval(()=>{
      countRef.current-=1; setCountdown(countRef.current);
      if(countRef.current<=0){
        countRef.current=POLL; setCountdown(POLL);
        fetchStats(); fetchReqs(); fetchCrit();
      }
    },1000);
    return()=>clearInterval(t);
  },[fetchStats,fetchReqs,fetchCrit]);

  useEffect(()=>{ const t=setInterval(fetchFeed,15000); return()=>clearInterval(t); },[fetchFeed]);

  return(
    <div style={{display:"flex",minHeight:"100vh"}}>
      <Sidebar active={page} onNav={setPage} critCount={critical.length} offline={offline}/>
      <div style={{flex:1,display:"flex",flexDirection:"column",minWidth:0}}>
        <TopBar page={page} countdown={countdown} loading={ldReqs}/>
        <main style={{flex:1,padding:18,overflowY:"auto"}}>
          {page==="overview"  && <OverviewPage   stats={stats} requests={requests} donors={donors} critical={critical} onAction={doAction} onView={setModal}/>}
          {page==="requests"  && <RequestsPage   requests={requests} loading={ldReqs}  onAction={doAction} onView={setModal}/>}
          {page==="donors"    && <DonorsPage     donors={donors}/>}
          {page==="analytics" && <AnalyticsPage  requests={requests} donors={donors}/>}
          {page==="critical"  && <CriticalPage   critical={critical} loading={ldCrit}  onAction={doAction}/>}
          {page==="upcoming"  && <UpcomingPage   predictions={predictions} loading={ldPred} onRun={runPred}/>}
          {page==="activity"  && <ActivityPage   feed={feed} loading={ldFeed} onRefresh={fetchFeed}/>}
        </main>
      </div>

      {modal&&(
        <DetailModal req={modal} onClose={()=>setModal(null)}
          onAction={doAction} add={add}/>
      )}
      <Toasts list={toasts}/>
    </div>
  );
}
