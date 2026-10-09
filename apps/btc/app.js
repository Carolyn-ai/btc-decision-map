/* BTC Sentinel decision map. The fixed topology explains the system; only committed events and observed book updates move light. */
window.BtcNetwork=(()=>{
  const NS='http://www.w3.org/2000/svg',WIDTH=1000,HEIGHT=3040;
  const layout={
    rest:[85,150,160,106,'orbit','◎'],trade:[335,120,166,112,'orbit','◉'],book:[335,330,166,112,'ladder','≋'],feature:[590,195,166,112,'hex','⌁'],quality:[788,195,170,112,'diamond','◆'],freeze:[780,468,178,112,'vault','▣'],
    v0:[85,915,168,98,'hex','◇'],v0choice:[575,915,168,98,'orbit','↗'],router:[85,1060,168,98,'gear','✦'],route:[332,1060,168,98,'hex','⌘'],v2choice:[575,1060,168,98,'orbit','↗'],jev:[85,1205,168,98,'hex','☁'],jevcall:[332,1205,168,98,'hex','⇄'],jevchoice:[575,1205,168,98,'orbit','↗'],lock:[782,1045,174,118,'diamond','◆'],truth:[782,1245,174,112,'orbit','◉'],score:[332,1310,210,78,'gauge','◕'],
    window:[75,1650,170,108,'vault','▤'],eval:[290,1650,170,108,'gear','◷'],risk:[505,1650,170,108,'diamond','◆'],intent:[720,1650,170,108,'ticket','⇢'],quote:[720,1840,170,108,'orbit','◎'],cost:[505,1840,170,108,'gauge','◕'],fill:[290,1840,170,108,'ticket','✓'],account0:[75,2025,170,108,'wallet','₿'],account2:[290,2025,170,108,'wallet','₿'],benchmark:[505,2025,170,108,'gauge','≋'],
    teacher:[75,2460,170,110,'orbit','✧'],manifest:[290,2460,170,110,'vault','▤'],candidate:[505,2460,170,110,'hex','✦'],shadow:[720,2460,170,110,'orbit','◌'],forward:[720,2630,170,110,'gauge','↗'],gate:[505,2630,170,110,'diamond','◆'],qualified:[290,2630,170,110,'vault','✓'],audit:[75,2630,170,110,'ladder','▥'],export:[75,2780,170,88,'ticket','⇩']
  };
  const displayTitles={rest:'公开价格',trade:'真实成交',book:'买卖报价',feature:'整理线索',quality:'数据够新吗',freeze:'记下当时信息',v0:'蓝：直接问',v0choice:'蓝：猜涨跌',router:'绿：先选方法',route:'规则或 Laya',v2choice:'绿：猜涨跌',jev:'紫：Jev 云端',jevcall:'实际接口调用',jevchoice:'紫：猜涨跌',lock:'事前留存答案',truth:'真实价格揭晓',score:'三路同题成绩',window:'蓝绿最近答案',eval:'30 秒检查',risk:'安全检查',intent:'准备买或卖',quote:'等新报价',cost:'算进费用',fill:'模拟成交',account0:'蓝色账户',account2:'绿色账户',benchmark:'和简单做法比',teacher:'ChatGPT 建议',manifest:'固定旧规则',candidate:'待测新方法',shadow:'先旁观测试',forward:'看未来结果',gate:'够证据了吗',qualified:'谨慎使用',audit:'保存过程',export:'下载记录'};
  const N=[
    ['rest',24,67,'行情','公开价格','电脑从交易所公开信息里取价格。收到回复和真的出现新成交，是两件不同的事。'],
    ['trade',184,28,'行情','真实成交','这里显示交易所已经发生的买卖。电脑用它来判断，也用后来的成交核对答案。'],
    ['book',184,106,'行情','买卖报价','这些是当前有人愿意买和卖的价格、数量，供模拟买卖前检查。'],
    ['feature',344,67,'行情','整理线索','电脑只整理答题前已经看到的价格和买卖信息。'],
    ['quality',504,67,'行情','数据够新吗','数据过旧或电脑时间有问题时，模拟买卖会暂停。'],
    ['freeze',664,67,'行情','记下当时信息','三路使用同一份事前冻结行情；蓝色和 Jev 读取相同价格路径文本，绿色从快照派生特征。事后价格不能塞回题目里。'],
    ['v0',824,28,'判断','蓝色：直接问 Laya','把同一份当时信息直接交给这台电脑上的 Laya，并记录实际回答用时。'],
    ['v0choice',984,28,'判断','蓝色猜涨跌','蓝色方法先写下答案：接下来涨，还是跌。'],
    ['router',824,106,'判断','绿色：先选方法','先用预先写好的规则判断这题该用固定方法，还是让本机 Laya 回答。'],
    ['route',984,106,'判断','本题实际用了什么','这里会显示绿色方法这一题到底用了规则，还是用了 Laya。'],
    ['v2choice',1144,106,'判断','绿色猜涨跌','绿色方法也要在揭晓真实价格前交答案，不能事后更改。'],
    ['jev',824,184,'判断','紫色：Jev 云端','同一份冻结行情另送给 Jev，通过 Vercel 云端作答，与蓝绿两路并行。'],
    ['jevcall',984,184,'判断','Jev 实际调用','只显示当前题实际返回的耗时或错误。调用上限暂停时不补造答案，不把以前答案当成此刻。'],
    ['jevchoice',1144,184,'判断','紫色猜涨跌','Jev 答案在本轮开始前返回并保存才有效；迟到与错误单独记录。它只比较决策，没有模拟账户。'],
    ['lock',1304,67,'判断','先记下答案','三路分别在开题前保存答案。只有三路都按时并拿到有效真实标签，才进入共同计分；蓝绿原有账户仍按原规则。'],
    ['truth',1464,28,'判断','真实价格揭晓','答题结束后，用新的真实成交核对涨跌；平局或数据不够会单独记。'],
    ['score',1464,106,'判断','猜对了几次','三路累计成绩只计算三路都按时、同一快照且真实涨跌标签为 primary 的共同题目。'],
    ['window',24,423,'执行','蓝绿最近的答案','只有蓝绿两路进入两个虚拟账户。每 30 秒检查一次，最多参考前面 6 次已提交判断；Jev 不接入账户。'],
    ['eval',194,423,'执行','30 秒检查','这一刻才考虑虚拟账户要不要买、卖，或什么都不做。'],
    ['risk',364,423,'执行','安全检查','资金限额、数据时效和费用不过关时，电脑会选择不买卖。'],
    ['intent',534,423,'执行','准备买或卖','先确定要买还是卖以及数量，然后才等待新的市场报价。'],
    ['quote',704,423,'执行','等新报价','只用决定之后新收到、又足够及时的报价来算模拟成交。'],
    ['cost',874,423,'执行','算进费用','模拟价格会加上费用和可能的成交价偏差；猜对方向仍可能亏钱。'],
    ['fill',1044,423,'执行','模拟成交','前面所有检查都通过，虚拟账户才会记一笔买卖。'],
    ['account0',1214,390,'执行','蓝色虚拟账户','与绿色账户从相同虚拟资金出发，单独记录现金和比特币。'],
    ['account2',1214,465,'执行','绿色虚拟账户','绿色方法的模拟买卖和费用记在自己的账户里，不和蓝色混算。'],
    ['benchmark',1384,423,'执行','和简单做法比','除了比蓝绿两种方法，也和一直拿现金、开头买入后不动相比。'],
    ['teacher',24,725,'研究','ChatGPT 的建议','ChatGPT 参与离线设计和检查；目前每一题运行时没有调用 ChatGPT。'],
    ['manifest',194,725,'研究','固定旧规则','先保存这一版的规则，后来提出的新方案不能改写旧成绩。'],
    ['candidate',364,725,'研究','待测新方法','电脑可能提出一个小改动，但此时还不知道它是否真的更好。'],
    ['shadow',534,725,'研究','先旁观测试','新方法也对未来新题作答，却暂时不接触蓝绿两个虚拟账户。'],
    ['forward',704,725,'研究','看未来结果','只计算新方法提出以后真正出现的新题，不能拿过去的题目充数。'],
    ['gate',874,725,'研究','证据够了吗','预先规定至少经过 7 天、拿到 5000 个有效结果，再讨论是否采用。'],
    ['qualified',1044,725,'研究','谨慎使用','如果扣掉费用后的证据仍不够，就继续持有现金。'],
    ['audit',1214,725,'研究','保存过程','关键动作、发生时间和当时的规则都留在这台电脑的记录里。'],
    ['export',1384,725,'研究','下载记录','可以下载原始记录，自己核对页面上展示的每一步。']
  ].map(([id,_x,_y,scene,title,detail])=>{const [x,y,w,h,shape,icon]=layout[id];return{id,x,y,w,h,shape,icon,scene,title,displayTitle:displayTitles[id]||title,detail};});
  const micro=(prefix,count,x,y,stepX,stepY,columns,w,h,scene,title,shape)=>Array.from({length:count},(_,i)=>({id:`${prefix}-${i}`,x:x+(i%columns)*stepX,y:y+Math.floor(i/columns)*stepY,w,h,scene,title:`${title} ${String(i+1).padStart(2,'0')}`,detail:'等待这一路的真实记录。',shape,micro:true}));
  const M=[...micro('trade-slot',24,59,595,74,40,12,61,30,'行情','成交','pill'),...micro('book-slot',20,52,685,94,39,10,82,30,'行情','报价','bar'),...micro('round-slot',24,59,1400,74,41,12,61,31,'判断','题目','hex'),...micro('order-slot',12,68,2170,151,46,6,132,37,'执行','模拟买卖','ticket'),...micro('event-slot',16,55,2880,113,45,8,98,36,'研究','保存记录','orb')];
  const nodeMap=new Map([...N,...M].map(n=>[n.id,n]));
  const E=[
    ['rest-trade','rest','trade','market'],['rest-book','rest','book','market'],['trade-feature','trade','feature','market'],['book-feature','book','feature','market'],['feature-quality','feature','quality','market'],['quality-freeze','quality','freeze','market'],
    ['freeze-v0','freeze','v0','base'],['v0-choice','v0','v0choice','base'],['freeze-router','freeze','router','opt'],['router-route','router','route','opt'],['route-v2','route','v2choice','opt'],['choice0-lock','v0choice','lock','base'],['choice2-lock','v2choice','lock','opt'],['freeze-jev','freeze','jev','jev'],['jev-call','jev','jevcall','jev'],['jev-choice','jevcall','jevchoice','jev'],['choicej-lock','jevchoice','lock','jev'],['lock-truth','lock','truth','verify'],['truth-score','truth','score','verify'],
    ['window-eval','window','eval','capital'],['eval-risk','eval','risk','capital'],['risk-intent','risk','intent','capital'],['intent-quote','intent','quote','capital'],['quote-cost','quote','cost','capital'],['cost-fill','cost','fill','capital'],['fill-account0','fill','account0','capital'],['fill-account2','fill','account2','capital'],['account0-benchmark','account0','benchmark','capital'],['account2-benchmark','account2','benchmark','capital'],
    ['teacher-manifest','teacher','manifest','research'],['manifest-candidate','manifest','candidate','research'],['candidate-shadow','candidate','shadow','research'],['shadow-forward','shadow','forward','research'],['forward-gate','forward','gate','research'],['gate-qualified','gate','qualified','research'],['qualified-audit','qualified','audit','research'],['audit-export','audit','export','research'],
    ['lock-window','lock','window','bridge'],['freeze-candidate','freeze','candidate','bridge'],['truth-forward','truth','forward','bridge'],['account-audit','account2','audit','bridge']
  ].map(([id,from,to,kind])=>({id,from,to,kind}));
  const scenes={
    all:{box:[0,0,WIDTH,HEIGHT],label:'全流程 / 每一步都能点开',title:'沿着光线往下看，它怎么做决定',detail:'公开行情先冻结，蓝、绿、紫三路并行判断并核对结果。只有蓝绿两路继续进入风险、费用与模拟账户检查。',summary:'真实行情 → 猜涨跌 → 验证 → 模拟买卖 → 检验改进'},
    market:{box:[0,0,WIDTH,770],start:0,label:'第一段 / 价格从哪来',title:'先确认价格是真的，而且足够新',detail:'交易所已经发生的成交，与当前买卖报价分别进入系统。只用回答前已经看到的信息。',summary:'收到数据不等于刚好有人成交'},
    signal:{box:[0,780,WIDTH,730],start:780,label:'第二段 / 三种方法并行猜涨跌',title:'同一份行情，蓝绿紫三路各交答案',detail:'蓝色直接问本机 Laya；绿色按教师框架选规则或 Laya；紫色并行调用云端 Jev。分别先保存答案，再用真实价格核对。',summary:'下方的小图形是已经保存的每一题'},
    policy:{box:[0,1520,WIDTH,510],start:1520,label:'第三段 / 能不能买卖',title:'猜对涨跌，也不能马上买',detail:'每 30 秒才检查一次最近的判断；行情不够新、风险太高或费用太贵时，就保持现金。',summary:'不买也是系统做出的决定'},
    execution:{box:[0,1810,WIDTH,510],start:1810,label:'第四段 / 模拟买卖结果',title:'等到新的报价，再记入虚拟账户',detail:'只有决定之后收到的新报价，才能用来算模拟成交。下面的记录和两套账户都只用虚拟资金。',summary:'这里没有向交易所发真实订单'},
    research:{box:[0,2320,WIDTH,720],start:2320,label:'第五段 / 怎样检验改进',title:'新方法先用未来数据考试',detail:'ChatGPT 参与离线设计；新方法先旁观真实新数据，证据不够就不改变账户规则。',summary:'至少 7 天、5000 个有效结果是预设门槛'}
  };
  let scene='all',stage=false,selected=null,initialized=false,latest=null,bookSeen=null,jevSeen=null,particles=[],frame=null,viewFrame=null,currentBox=[0,0,WIDTH,HEIGHT];
  const microSeen={trade:null,book:null,round:null,order:null,event:null};
  const by=id=>document.getElementById(id),svg=(tag,attrs={})=>{const el=document.createElementNS(NS,tag);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,String(v));return el;};
  const fmt=(value,digits=0)=>value!=null&&Number.isFinite(Number(value))?Number(value).toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}):'—';
  const usd=(value,digits=0)=>value!=null&&Number.isFinite(Number(value))?`$${fmt(value,digits)}`:'—';
  const pct=value=>value!=null&&Number.isFinite(Number(value))?`${fmt(Number(value)*100,1)}%`:'—';
  const secs=value=>value!=null&&Number.isFinite(Number(value))?`${fmt(value,1)}s`:'—';
  const when=value=>Number(value)>0?new Date(Number(value)*1000).toLocaleTimeString('zh-CN',{hour12:false}):'—';
  const choice=value=>value==='higher'?'▲ 看高':value==='lower'?'▼ 看低':'等待判断';
  const value=(id,v)=>{const el=by(`graph-value-${id}`);if(el)el.textContent=String(v)};
  function pathFor(e){const a=nodeMap.get(e.from),b=nodeMap.get(e.to),ax=a.x+a.w/2,ay=a.y+a.h/2,bx=b.x+b.w/2,by=b.y+b.h/2,dy=by-ay;
    if(e.from==='freeze'&&['v0','router','jev'].includes(e.to)){const x={v0:25,router:35,jev:45}[e.to];return `M${ax} ${ay} C${ax} 730,${x} 730,${x} 900 V${by} H${bx}`;}
    if(Math.abs(dy)<55){const dx=bx-ax;return `M${ax} ${ay} C${ax+dx*.45} ${ay-24},${bx-dx*.45} ${by-24},${bx} ${by}`;}
    return `M${ax} ${ay} C${ax} ${ay+dy*.5},${bx} ${by-dy*.5},${bx} ${by}`;
  }
  function shell(n){const w=n.w,h=n.h,cx=w/2,cy=h/2,shape=n.shape;
    if(shape==='orbit'){const outer=svg('circle',{cx,cy,r:Math.min(w,h)/2-5,class:'node-shell'});return [outer,svg('circle',{cx,cy,r:Math.min(w,h)/2-15,class:'node-inner'})];}
    if(shape==='hex'||shape==='vault'){const points=`${w*.24},4 ${w*.76},4 ${w-3},${h/2} ${w*.76},${h-4} ${w*.24},${h-4} 3,${h/2}`;return [svg('polygon',{points,class:'node-shell'}),svg('path',{d:`M${w*.27} 13 H${w*.73} M${w*.27} ${h-13} H${w*.73}`,class:'node-inner-line'})];}
    if(shape==='diamond')return [svg('polygon',{points:`${cx},3 ${w-3},${cy} ${cx},${h-3} 3,${cy}`,class:'node-shell'}),svg('circle',{cx,cy,r:Math.min(w,h)*.34,class:'node-inner'})];
    if(shape==='ticket')return [svg('path',{d:`M12 4 H${w-12} L${w-4} 14 V${h*.37} Q${w-17} ${h/2} ${w-4} ${h*.63} V${h-14} L${w-12} ${h-4} H12 L4 ${h-14} V${h*.63} Q17 ${h/2} 4 ${h*.37} V14 Z`,class:'node-shell'}),svg('path',{d:`M26 ${h-16} H${w-26}`,class:'node-inner-line'})];
    if(shape==='gear'){const points=Array.from({length:16},(_,i)=>{const a=(i/16)*Math.PI*2-Math.PI/2,r=i%2?Math.min(w,h)*.39:Math.min(w,h)*.48;return `${cx+Math.cos(a)*r},${cy+Math.sin(a)*r}`}).join(' ');return [svg('polygon',{points,class:'node-shell'}),svg('circle',{cx,cy,r:Math.min(w,h)*.3,class:'node-inner'})];}
    if(shape==='gauge')return [svg('rect',{x:4,y:4,width:w-8,height:h-8,rx:29,class:'node-shell'}),svg('path',{d:`M${cx-39} ${h-19} A48 48 0 0 1 ${cx+39} ${h-19}`,class:'node-inner-line'})];
    if(shape==='wallet')return [svg('rect',{x:3,y:5,width:w-6,height:h-10,rx:19,class:'node-shell'}),svg('path',{d:`M${w*.55} 23 H${w-3} V${h-23} H${w*.55} Q${w*.5} ${cy} ${w*.55} 23 Z`,class:'node-inner-line'})];
    return [svg('rect',{x:4,y:4,width:w-8,height:h-8,rx:15,class:'node-shell'}),svg('path',{d:`M19 21 H${w-19} M19 ${h-21} H${w-19}`,class:'node-inner-line'})];
  }
  function microShell(n){const w=n.w,h=n.h;
    if(n.shape==='hex')return svg('polygon',{points:`12,1 ${w-12},1 ${w-1},${h/2} ${w-12},${h-1} 12,${h-1} 1,${h/2}`,class:'node-shell'});
    if(n.shape==='ticket')return svg('path',{d:`M8 2 H${w-8} V${h*.36} Q${w-17} ${h/2} ${w-8} ${h*.64} V${h-2} H8 V${h*.64} Q17 ${h/2} 8 ${h*.36} Z`,class:'node-shell'});
    if(n.shape==='orb')return svg('circle',{cx:18,cy:h/2,r:15,class:'node-shell'});
    return svg('rect',{x:1,y:1,width:w-2,height:h-2,rx:n.shape==='pill'?h/2:6,class:'node-shell'});
  }
  function init(){if(initialized)return;initialized=true;
    const bg=by('network-backplane'),edgeLayer=by('network-edge-layer'),nodeLayer=by('network-node-layer');
    for(const [y,h,num,title,note,klass] of [[8,750,'01','价格从哪来','真实成交 · 买卖报价 · 当时看见的信息','market'],[780,730,'02','三种方法并行猜涨跌','蓝：Laya · 绿：教师框架 · 紫：Jev 云端 · 真实价格揭晓','signal'],[1520,790,'03','能不能模拟买卖','风险和费用过关 · 新报价 · 两套虚拟账户','execution'],[2320,710,'04','新方法如何证明自己','ChatGPT 离线建议 · 未来数据考试 · 保存原始记录','research']]){
      bg.appendChild(svg('rect',{x:13,y,width:974,height:h,rx:32,class:`graph-lane zone-${klass}`}));
      const idx=svg('text',{x:58,y:y+190,class:'graph-chapter-index'});idx.textContent=num;bg.appendChild(idx);
      const t=svg('text',{x:54,y:y+60,class:'graph-chapter-title'});t.textContent=title;bg.appendChild(t);
      const s=svg('text',{x:54,y:y+87,class:'graph-chapter-note'});s.textContent=note;bg.appendChild(s);
      bg.appendChild(svg('circle',{cx:884,cy:y+121,r:94,class:`chapter-ring ${klass}`}));
      bg.appendChild(svg('circle',{cx:884,cy:y+121,r:57,class:`chapter-ring inner ${klass}`}));
      for(let i=0;i<24;i++)bg.appendChild(svg('circle',{cx:42+(i*167+y/10)%916,cy:y+119+(i*113)%Math.max(150,h-150),r:i%5===0?2.2:1.2,class:'chapter-star'}));
    }
    for(const e of E)edgeLayer.appendChild(svg('path',{id:`edge-${e.id}`,d:pathFor(e),class:`graph-edge ${e.kind}`,'data-edge':e.id}));
    for(const [rack,y,parent] of [['trade',580,'trade'],['book',675,'book'],['round',1388,'score'],['order',2158,'fill'],['event',2868,'audit']]){
      const p=nodeMap.get(parent),cx=p.x+p.w/2,py=p.y+p.h/2;
      edgeLayer.appendChild(svg('path',{id:`edge-rack-${rack}`,d:`M${cx} ${py} C${cx} ${(py+y)/2},500 ${(py+y)/2},500 ${y} H53 M500 ${y} H948`,class:`rack-bus ${rack}`,'data-edge':`rack-${rack}`}));
      for(const n of M.filter(item=>item.id.startsWith(`${rack}-slot`)))edgeLayer.appendChild(svg('path',{d:`M${n.x+n.w/2} ${y} V${n.y}`,class:`rack-wire ${rack}`,'data-edge':`wire-${n.id}`}));
    }
    for(const n of N){const g=svg('g',{id:`graph-${n.id}`,class:`graph-node core-node shape-${n.shape} ${n.scene} ${n.id.startsWith('jev')?'jev-lane':''}`,'data-node':n.id,transform:`translate(${n.x} ${n.y})`,tabindex:'0',role:'button','aria-label':n.title});
      for(const part of shell(n))g.appendChild(part);
      const icon=svg('text',{x:n.w/2,y:31,class:'graph-node-icon','text-anchor':'middle'});icon.textContent=n.icon;g.appendChild(icon);
      const t=svg('text',{x:n.w/2,y:n.h/2+11,class:'graph-node-title','text-anchor':'middle'});t.textContent=n.displayTitle;g.appendChild(t);
      const v=svg('text',{id:`graph-value-${n.id}`,x:n.w/2,y:n.h/2+34,class:'graph-node-value','text-anchor':'middle'});v.textContent='—';g.appendChild(v);nodeLayer.appendChild(g);
    }
    for(const n of M){const g=svg('g',{id:`graph-${n.id}`,class:`graph-node micro-node shape-${n.shape} ${n.scene} ${n.id.startsWith('jev')?'jev-lane':''}`,'data-node':n.id,transform:`translate(${n.x} ${n.y})`,tabindex:'0',role:'button','aria-label':n.title});
      g.appendChild(microShell(n));
      if(n.shape==='bar')g.appendChild(svg('rect',{id:`graph-depth-${n.id}`,x:4,y:n.h-6,width:0,height:3,rx:1.5,class:'depth-fill'}));
      const offset=n.shape==='orb'?37:5;
      const t=svg('text',{id:`graph-title-${n.id}`,x:offset,y:12,class:'graph-node-title'});t.textContent=n.title;g.appendChild(t);
      const v=svg('text',{id:`graph-value-${n.id}`,x:offset,y:n.h-6,class:'graph-node-value'});v.textContent='—';g.appendChild(v);nodeLayer.appendChild(g);
    }
    nodeLayer.addEventListener('click',ev=>{const g=ev.target.closest('[data-node]');if(g)select(g.getAttribute('data-node'));});
    nodeLayer.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){const g=ev.target.closest('[data-node]');if(g){ev.preventDefault();select(g.getAttribute('data-node'));}}});
    document.querySelectorAll('[data-network-scene]').forEach(btn=>btn.addEventListener('click',()=>{const next=btn.dataset.networkScene;setScene(next);if(!stage){const top=next==='all'?0:scenes[next].start;const rect=by('network-svg').getBoundingClientRect();window.scrollTo({top:window.scrollY+rect.top+top/HEIGHT*rect.height-115,behavior:'instant'});}}));
    by('stage-toggle').addEventListener('click',()=>setStage(!stage));
    document.addEventListener('keydown',ev=>{if(ev.key==='Escape'&&stage)setStage(false)});
    setScene('all',false);
  }
  function setStage(on){stage=Boolean(on);document.body.classList.toggle('network-stage-mode',stage);by('stage-toggle').setAttribute('aria-pressed',String(stage));by('stage-toggle').textContent=stage?'退出放大 ×':'放大这一段 ↗';setScene(stage?(scene==='all'?'market':scene):'all');}
  function setScene(next,animate=true){if(!scenes[next])return;scene=next;selected=null;document.querySelectorAll('[data-network-scene]').forEach(b=>b.classList.toggle('active',b.dataset.networkScene===next));
    document.querySelectorAll('.graph-node').forEach(el=>el.classList.toggle('muted',stage&&next!=='all'&&!(next==='market'&&el.classList.contains('行情'))&&!(next==='signal'&&el.classList.contains('判断'))&&!(next==='policy'&&el.classList.contains('执行'))&&!(next==='execution'&&el.classList.contains('执行'))&&!(next==='research'&&el.classList.contains('研究'))));
    document.querySelectorAll('.graph-edge').forEach(el=>el.classList.toggle('muted',stage&&next!=='all'&&!(next==='market'&&el.classList.contains('market'))&&!(next==='signal'&&['base','opt','jev','verify'].some(k=>el.classList.contains(k)))&&!(next==='policy'&&el.classList.contains('capital'))&&!(next==='execution'&&el.classList.contains('capital'))&&!(next==='research'&&el.classList.contains('research'))));
    const data=scenes[next];by('network-scene-label').textContent=data.label;by('network-inspector-title').textContent=data.title;by('network-inspector-detail').textContent=data.detail;by('network-scene-summary').textContent=data.summary;by('network-inspector-value').textContent=next==='all'?'点一个图形，看此刻的数据':'数据仍在实时更新';
    const target=stage?data.box:scenes.all.box;
    if(viewFrame)cancelAnimationFrame(viewFrame);
    if(!animate||window.matchMedia('(prefers-reduced-motion: reduce)').matches){currentBox=[...target];by('network-svg').setAttribute('viewBox',currentBox.join(' '));return;}
    const start=[...currentBox],began=performance.now();
    function step(now){const t=Math.min(1,(now-began)/650),p=1-Math.pow(1-t,3);currentBox=start.map((v,i)=>v+(target[i]-v)*p);by('network-svg').setAttribute('viewBox',currentBox.join(' '));viewFrame=t<1?requestAnimationFrame(step):null;}
    viewFrame=requestAnimationFrame(step);
  }
  function select(id){const n=nodeMap.get(id);if(!n)return;selected=id;document.querySelectorAll('.graph-node.selected').forEach(el=>el.classList.remove('selected'));by(`graph-${id}`).classList.add('selected');by('network-scene-label').textContent=`正在看 / ${n.scene}`;by('network-inspector-title').textContent=n.displayTitle||n.title;by('network-inspector-detail').textContent=n.detail;by('network-inspector-value').textContent=by(`graph-value-${id}`).textContent;by('network-scene-summary').textContent='点旁边的图形，可以接着看下一步';}
  function renderMicro(d){
    const m=d.market||{},s=d.signal||{},p=d.portfolio||{};
    const trades=(Array.isArray(m.trades)?m.trades:[]).slice(-24);
    const levels=[...(Array.isArray(m.bids)?m.bids:[]).slice(0,10).map((row,i)=>({row,side:'买',level:i+1})),...(Array.isArray(m.asks)?m.asks:[]).slice(0,10).map((row,i)=>({row,side:'卖',level:i+1}))];
    const rounds=(Array.isArray(s.rounds)?s.rounds:[]).slice(0,24).reverse();
    const orders=(Array.isArray(p.orders)?p.orders:[]).slice(0,12).reverse();
    const events=(Array.isArray(d.events)?d.events:[]).filter(e=>e.kind!=='poll_heartbeat').slice(-16);
    const arrow=x=>x==='higher'?'▲':x==='lower'?'▼':'·';
    const groups={
      trade:{rows:trades,color:'#80dcf1',paint:(r,i)=>({title:`成交 ${String(i+1).padStart(2,'0')}`,value:fmt(r.price,0),detail:`交易所已成交 · ${when(r.time)} · ${r.side==='buy'?'买方主动成交':'卖方主动成交'} · 价格 ${usd(r.price,2)} · 数量 ${fmt(r.volume,6)} BTC`,key:`${r.id??r.time}:${r.price}`})},
      book:{rows:levels,color:'#82bed9',paint:r=>({title:`${r.side}价 ${String(r.level).padStart(2,'0')}`,value:fmt(r.row?.[0],0),detail:`第 ${r.level} 个${r.side==='买'?'有人愿意买':'有人愿意卖'}的价格 · ${usd(r.row?.[0],2)} · 数量 ${fmt(r.row?.[1],6)} BTC`,key:`${r.side}:${r.level}:${r.row?.[0]}:${r.row?.[1]}`})},
      round:{rows:rounds,color:'#a5e7d4',paint:r=>({title:`题目 ${when(r.start).slice(-8)}`,value:`${arrow(r.baseline?.choice)}/${arrow(r.optimized?.choice)}/${r.jev?.status==='on_time'?arrow(r.jev.choice):'·'}`,detail:`${when(r.start)} · 蓝色 ${r.baseline?.choice==='higher'?'猜涨':'猜跌'} / 绿色 ${r.optimized?.choice==='higher'?'猜涨':'猜跌'} / 紫色 ${r.jev?.status==='on_time'?(r.jev.choice==='higher'?'猜涨':'猜跌'):r.jev?.status==='late'?'迟到，不计分':r.jev?.status==='error'?'调用错误':'本题未调用'} · ${r.status==='settled'?'已揭晓':r.status==='locked'?'等待揭晓':r.status==='tie'?'涨跌打平':r.status==='void'?'数据不足':'尚未答完'} · ${r.label_tier==='primary'?'可计入公平对比':'不计入主成绩'}`,key:`${r.start}:${r.status}:${r.truth??''}:${r.jev?.completed_at??''}`})},
      order:{rows:orders,color:'#e6c77f',paint:r=>({title:`${r.account==='optimized'?'绿':'蓝'} · ${r.status==='filled'?'已模拟成交':'买卖记录'}`,value:`${r.side==='buy'?'买':'卖'} ${when(r.time).slice(-8)}`,detail:`${when(r.time)} · ${r.account==='optimized'?'绿色方法':'蓝色方法'} · ${r.side==='buy'?'想买入':'想卖出'} · ${r.status==='filled'?'已记入虚拟账户':'没有成交'} · 记录 ${r.order_id??'—'}`,key:`${r.order_id}:${r.status}`})},
      event:{rows:events,color:'#c2aaff',paint:r=>({title:(window.btcEventNames?.[r.kind]||'系统新记录').slice(0,8),value:`#${fmt(r.seq)}`,detail:`系统保存的第 ${r.seq} 条记录 · ${when(r.time)} · ${window.btcEventNames?.[r.kind]||'系统事件'}${r.round_id?` · 题目 ${when(r.round_id)}`:''}`,key:String(r.seq)})}
    };
    for(const [type,config] of Object.entries(groups)){
      const current=new Set(),previous=microSeen[type];let fresh=false;
      for(let i=0;i<({trade:24,book:20,round:24,order:12,event:16})[type];i++){
        const n=nodeMap.get(`${type}-slot-${i}`),r=config.rows[i];if(!n)continue;const g=by(`graph-${n.id}`);if(!g)continue;
        if(!r){n.detail='这里还没有新记录。';g.classList.add('empty');value(n.id,'—');by(`graph-title-${n.id}`).textContent=type==='round'?'暂无题目':n.title;continue;}
        const item=config.paint(r,i);n.title=item.title;n.detail=item.detail;g.setAttribute('aria-label',item.title);g.classList.remove('empty');by(`graph-title-${n.id}`).textContent=item.title;value(n.id,item.value);current.add(item.key);
        if(type==='book'){const depth=by(`graph-depth-${n.id}`),volume=Number(r.row?.[1]||0);if(depth)depth.setAttribute('width',String(Math.max(2,Math.min(n.w-8,volume/3*(n.w-8)))));}
        if(previous&&!previous.has(item.key)){pulse(n.id);fresh=true;}
      }
      if(fresh)flow([`rack-${type}`],config.color);
      microSeen[type]=current;
    }
  }
  function render(d){init();latest=d;const m=d.market||{},h=d.health||{},f=m.features||{},s=d.signal||{},metric=s.metrics||{},p=d.portfolio||{},stats=p.stats||{},a=p.accounts||{},ev=d.evolution||{},row=d.network_round||(s.latest?.manifest_hash===ev.active_manifest?.hash?s.latest:{}),candidate=(ev.candidates||[]).at(-1),progress=candidate?.progress||{};
    const trades=Array.isArray(m.trades)?m.trades:[],last=trades.at(-1),price=last?.price??m.ticker?.last;
    value('rest',secs(h.feed_age_s??m.source_age_s?.trades));value('trade',price!=null?usd(price,0):'等待成交');
    value('book',h.book_age_s!=null?`收到 ${secs(h.book_age_s)}`:'等待报价');value('feature',f.recent_trade_count_90s!=null?`${fmt(f.recent_trade_count_90s)} 笔 / 90 秒`:'收集价格');
    value('quality',h.paused_reason?'暂停模拟买卖':m.ready===false?'等真实数据':'数据已连接');value('freeze',row.frozen_at?when(row.frozen_at):'等待题目');
    value('v0',row.baseline?.model_ms!=null?`${fmt(row.baseline.model_ms,1)} 毫秒`:'等待 Laya');value('v0choice',choice(row.baseline?.choice));
    value('router',row.optimized?.route==='15s_momentum_rule'?'固定规则':row.optimized?.route==='laya'?'本机 Laya':'等待选择');value('route',row.optimized?.model_ms!=null?`${fmt(row.optimized.model_ms,1)} 毫秒`:'等待判断');value('v2choice',choice(row.optimized?.choice));
    const j=row.jev,comparison=d.jev_comparison||{};
    value('jev',j?'本题已调用':comparison.disabled_reason?'调用已暂停':'等待新题');
    value('jevcall',j?.latency_ms!=null?`${fmt(j.latency_ms,1)} 毫秒`:comparison.max_calls>0&&comparison.calls>=comparison.max_calls?'已到调用上限':'等待接口返回');
    value('jevchoice',j?.status==='on_time'?choice(j.choice):j?.status==='late'?'迟到，不计分':j?.status==='error'?'调用失败':comparison.disabled_reason?'本题未调用':'等待判断');
    nodeMap.get('jevcall').detail=j?`本题 ${when(row.start)} · HTTP ${j.http_status??'未返回'} · ${fmt(j.latency_ms,1)} 毫秒 · 返回 ${when(j.completed_at)} · ${j.status==='on_time'?'按时保存':j.status==='late'?'迟到，不计分':j.error||'调用失败'}`:`本题没有 Jev 调用记录。${comparison.disabled_reason||'等待新的冻结题目。'} 最近保存的调用来自 ${when(comparison.latest?.start)}，不当作本题答案。`;
    const saved=(row.locked_at&&row.locked_at<row.start?2:0)+(j?.status==='on_time'?1:0);
    value('lock',`${saved} / 3 路已保存`);value('truth',row.status==='tie'?'涨跌打平':row.truth?choice(row.truth):row.status==='void'?'数据不足':'等待揭晓');value('score',`${fmt(comparison.shared_primary||0)} 道共同题`);
    if(!d.network_round){const stamp=comparison.latest?.completed_at;if(jevSeen!=null&&stamp!=null&&stamp!==jevSeen){const actual=comparison.latest;flow(actual.status==='on_time'?['freeze-jev','jev-call','jev-choice','choicej-lock']:['freeze-jev','jev-call'],'#c4a2ff');pulse(actual.status==='on_time'?'jevchoice':'jevcall');}jevSeen=stamp??jevSeen;}
    value('window','最多看 6 题');value('eval',stats.evaluations!=null?`${fmt(stats.evaluations)} 次检查`:'等待检查');value('risk',h.paused_reason?'暂停买卖':'正在检查');value('intent',stats.orders!=null?`${fmt(stats.orders)} 次准备`:'等待决定');
    value('quote',stats.depth_probe_2s_rate!=null?`${pct(stats.depth_probe_2s_rate)} 及时`:'等待新报价');value('cost',stats.cost_bps_one_way!=null?`单次约 ${fmt(stats.cost_bps_one_way/100,2)}%`:'费用待定');value('fill',stats.fills!=null?`${fmt(stats.fills)} 笔模拟`:'等待模拟买卖');
    value('account0',a.baseline?.equity!=null?usd(a.baseline.equity,0):'等待金额');value('account2',a.optimized?.equity!=null?usd(a.optimized.equity,0):'等待金额');value('benchmark','两种简单做法');
    value('teacher','离线建议');value('manifest',ev.active_manifest?.hash?`版本 ${ev.active_manifest.hash.slice(0,6)}`:'等待版本');value('candidate',candidate?'有方案待测':'暂无新方案');value('shadow',candidate?'只测试不买卖':'暂无新方案');
    value('forward',candidate?`${fmt(progress.valid_labels??0)} 题有结果`:'等待未来题目');value('gate',candidate?`${fmt(progress.valid_labels??0)} / ${fmt(progress.required_valid??5000)}`:'至少 5000 题');value('qualified',(ev.qualified_policy||[])[0]?.status==='hold'?'保持现金':'独立检查');value('audit',d.event_seq!=null?`第 ${fmt(d.event_seq)} 条`:'等待记录');value('export','原始记录');
    if(d.network_round&&!selected){by('network-scene-label').textContent=`回看 ${when(row.start)} / 过去保存的题目`;by('network-scene-summary').textContent='三路判断来自这一题的保存记录；没有再次调用模型。';by('network-inspector-value').textContent=`这题 ${saved} / 3 路已保存`;}
    renderMicro(d);
    if(selected)by('network-inspector-value').textContent=by(`graph-value-${selected}`).textContent;
    const bookStamp=m.source_times?.book; if(bookStamp!=null&&bookSeen!=null&&bookStamp!==bookSeen){flow(['rest-book','book-feature'],'#89c8e7');pulse('book');}bookSeen=bookStamp??bookSeen;
  }
  function pulse(id){const el=by(`graph-${id}`);if(!el)return;el.classList.remove('active');void el.getBoundingClientRect();el.classList.add('active');setTimeout(()=>el.classList.remove('active'),1250);}
  function flow(ids,color){if(window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;for(const id of ids){const path=by(`edge-${id}`);if(!path)continue;path.classList.add('energized');setTimeout(()=>path.classList.remove('energized'),1450);const group=by('network-particles');for(let i=0;i<3;i++){const c=svg('circle',{r:i===0?5.2:i===1?3.5:2.2,fill:color,class:'graph-particle'});group.appendChild(c);particles.push({path,node:c,start:performance.now()+i*95,duration:id==='lock-window'||id==='truth-forward'?1500:920});}}if(!frame)frame=requestAnimationFrame(tick);}
  function tick(now){particles=particles.filter(p=>{const t=(now-p.start)/p.duration;if(t>=1){p.node.remove();return false;}if(t<0)return true;const q=t*t*(3-2*t),at=p.path.getPointAtLength(p.path.getTotalLength()*q);p.node.setAttribute('cx',at.x);p.node.setAttribute('cy',at.y);p.node.setAttribute('opacity',Math.min(1,Math.sin(Math.PI*t)*1.8+.12));return true;});frame=particles.length?requestAnimationFrame(tick):null;}
  function animate(e){if(!initialized)return;switch(e.kind){
    case 'new_trade_received':flow(['rest-trade','trade-feature'],'#80dcf1');pulse('trade');break;
    case 'snapshot_frozen':flow(['feature-quality','quality-freeze'],'#80dcf1');pulse('freeze');break;
    case 'baseline_model_done':flow(['freeze-v0','v0-choice'],'#73c9ff');pulse('v0choice');break;
    case 'candidate_model_done':case 'optimized_raw':flow(['freeze-router','router-route','route-v2'],'#77efcd');pulse('v2choice');break;
    case 'decision_locked':flow(['choice0-lock','choice2-lock'],'#c5f6e5');pulse('lock');break;
    case 'settled':flow(e.label_tier==='primary'?['lock-truth','truth-score','truth-forward']:['lock-truth','truth-forward'],'#e6d28b');pulse('truth');break;
    case 'tie':case 'void':flow(['lock-truth'],'#b5a989');pulse('truth');break;
    case 'portfolio_evaluation':flow(['window-eval','eval-risk'],'#e6c77f');pulse('eval');break;
    case 'blocked':case 'timeout':pulse('risk');break;
    case 'order_intent':flow(['risk-intent'],'#e6c77f');pulse('intent');break;
    case 'depth_probe':flow(['intent-quote'],'#e6c77f');pulse('quote');break;
    case 'gate_pass':flow(['quote-cost'],'#e6c77f');pulse('cost');break;
    case 'paper_fill':flow(['cost-fill',e.account==='optimized'?'fill-account2':'fill-account0'],'#e6c77f');pulse('fill');pulse(e.account==='optimized'?'account2':'account0');break;
    case 'account_mark':flow(['account0-benchmark','account2-benchmark'],'#e3d49d');pulse('benchmark');break;
    case 'candidate_frozen':flow(['manifest-candidate'],'#c2aaff');pulse('candidate');break;
    case 'shadow_candidate_decision':flow(['candidate-shadow'],'#c2aaff');pulse('shadow');break;
    case 'candidate_forward_complete':flow(['shadow-forward','forward-gate'],'#c2aaff');pulse('gate');break;
    case 'qualified_policy_evaluation':flow(['gate-qualified'],'#c2aaff');pulse('qualified');break;
    default:break;
  }}
  return {init,render,animate,setStage,setScene,nodeCount:N.length+M.length,edgeCount:E.length+M.length+5};
})();


/* BTC / SENTINEL. All activity comes from /api/btc/state; this file never predicts or trades. */
const $ = id => document.getElementById(id);
const S = {live:null,view:null,mode:'live',priceMode:'trades',busy:false,seenSeq:null,
  particles:[],animationFrame:null,priceSignature:null,tapeSignature:null,selectedRound:null,
  serverOffset:0,queued:0,chartHover:null,equityScale:null,replayTrades:null,replayPoints:null,replayOrders:null};
const money = value => value!=null&&value!==''&&Number.isFinite(Number(value)) ? `${Number(value)<0?'−':''}$${Math.abs(Number(value)).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}` : '—';
const number = (value, digits=2) => value!=null&&value!==''&&Number.isFinite(Number(value)) ? Number(value).toLocaleString('en-US',{minimumFractionDigits:digits,maximumFractionDigits:digits}) : '—';
const signed = (value,digits=2) => value!=null&&Number.isFinite(Number(value)) ? `${Number(value)>0?'+':''}${Number(value).toFixed(digits)}%` : '—';
const time = value => Number.isFinite(Number(value)) && Number(value)>0 ? new Date(Number(value)*1000).toLocaleTimeString('zh-CN',{hour12:false}) : '—';
const dateTime = value => Number.isFinite(Number(value)) && Number(value)>0 ? new Date(Number(value)*1000).toLocaleString('zh-CN',{hour12:false}) : '—';
const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const text = (id,value) => {const el=$(id); if(el) el.textContent=value;};
const asArray = value => Array.isArray(value) ? value : [];
const first = (...items) => items.find(item=>item!==undefined && item!==null);
const fraction = value => {const x=Number(value); if(!Number.isFinite(x)) return null; return x>1?x/100:x;};
const dir = value => value==='higher'?'▲ 猜涨':value==='lower'?'▼ 猜跌':value==='tie'?'— 打平':'—';
const age = value => value!=null&&Number.isFinite(Number(value)) && Number(value)>=0 ? `${Number(value).toFixed(1)} 秒` : '—';
const roundId = row => first(row?.round_id,row?.start,row?.id);
const eventRound = event => first(event?.round_id,event?.start,event?.round);
const activeHash = d => d?.evolution?.active_manifest?.hash;
const currentRounds = d => asArray(d?.signal?.rounds).filter(row=>activeHash(d)&&row.manifest_hash===activeHash(d));
const currentLatest = d => {const row=d?.signal?.latest;return row&&activeHash(d)&&row.manifest_hash===activeHash(d)?row:null;};
const freshClass = (el,old,bad) => {el.classList.toggle('stale',Boolean(old));el.classList.toggle('offline',Boolean(bad));};
const modelMs = row => first(row?.model_ms,row?.raw?.model_ms);
const statusLabel = value => ({settled:'真实结果已揭晓',tie:'涨跌打平',void:'数据不够，不能判',locked:'答案已提交',frozen:'已记下当时信息',partial:'只有一边回答',missed:'没赶上截止',open:'等真实结果',evaluated:'已检查',intent:'准备买卖',paper_fill:'已模拟成交',blocked:'安全检查未过',timeout:'等新报价超时',hold:'继续拿现金',buy:'准备买入',sell:'准备卖出',filled:'已模拟成交',unfilled:'没有成交',frozen_shadow:'新方法单独测试',collecting_forward_evidence:'正在看未来结果',awaiting_40_primary_training_rounds:'还需更多有结果的题',rejected:'暂不采用',eligible:'达到预设测试数量',promoted:'已登记为待测方法',online:'在线',ok:'正常',paused:'已暂停'})[value] || (value ? '其他情况（可看原始记录）' : '等待');
const reasonLabel = value => ({insufficient_locked_signals:'可参考的判断还不够',balanced_signals:'最近涨跌判断打平',at_target_weight:'账户已经达到预定比例',stale_mark:'账户金额太久没更新',asset_rules_unavailable:'交易规则暂时不可用',asset_pair_offline:'这个市场暂时不可用',cooldown:'暂时休息，稍后再检查',daily_budget_exhausted:'今天允许的费用已用完',below_asset_minimum:'买卖数量太小',daily_loss_limit:'今天的亏损已达上限',daily_order_limit:'今天的买卖次数已达上限',quote_timeout:'没有及时等到新报价',invalid_book:'买卖报价不可靠',exploration_signal:'最近的判断支持检查买卖',no_qualified_snapshot:'当时的市场信息不够可靠',not_locked_before_start:'答案没在截止前提交',restart_before_pair_lock:'电脑重启前两边未答完',late_commit:'答案交得太晚',missing_boundary_trade:'关键时刻缺少真实成交',trade_poll_gap:'两次读取成交相隔太久',possible_cursor_gap:'交易所记录可能有缺口',clock_jump:'电脑时间突然变化',uncalibrated_one_hour_gross_return_vs_total_cost:'还不能证明收益超过全部费用',insufficient_forward_samples_or_coverage:'未来测试题目还不够',predeclared_signal_gate_passed:'达到预先写下的条件',invalid_or_wide_book:'报价不可靠或买卖价差太大',insufficient_probe_depth:'可买卖的数量不够',stale_probe_mark:'账户金额更新太慢',probe_price_jump:'新报价跳动太大',empty_book:'现在没有可用的买卖报价',quote_timeout_or_invalid_time:'新报价太晚或时间有问题',quote_invalid:'新报价不可用',quote_error:'读取新报价失败',quote_jump:'新报价跳动太大',quote_time_invalid:'报价时间有问题',quote_precedes_intent:'报价早于买卖决定',stale_quote_source:'报价太旧',stale_or_invalid_mark:'账户金额不可靠',fill_rejected:'模拟成交检查未过',insufficient_cash:'现金不够',insufficient_btc:'持有的比特币不够',invalid_order_size:'买卖数量不合适',invalid_equity:'账户金额不可靠',no_order_intent:'这次没有决定买卖',missing_intent_mark:'决定买卖时缺少账户金额',stale_account_revision:'账户状态已经变化',ok:'正常'})[value] || (value ? '其他原因（可看原始记录）' : '待记录');

function setMode(mode,note=''){
  S.mode=mode;
  const banner=$('mode-banner'),shade=$('replay-shade');
  banner.hidden=mode==='live';shade.hidden=mode!=='replay';
  if(mode==='paused') {text('mode-banner-title','画面已暂停');text('mode-banner-note',note||'只有画面暂停，电脑仍在记录新的行情和判断。');text('pause-btn','继续实时');}
  if(mode==='replay') {text('mode-banner-title','正在看上一轮');text('mode-banner-note',note||'现在展示过去保存的一题，不是此刻的市场。');text('pause-btn','返回实时');}
  if(mode==='live') {S.view=S.live;S.selectedRound=null;S.replayTrades=null;S.replayPoints=null;S.replayOrders=null;S.queued=0;S.priceSignature=null;text('pause-btn','暂停画面');text('price-cadence','只有交易所出现新成交，这条线才更新');text('equity-empty','账户记录还不够，暂时画不出可靠曲线');if(S.live){S.seenSeq=first(S.live.event_seq,asArray(S.live.events).at(-1)?.seq,S.seenSeq);render(S.live,true);}}
}

function canvasContext(canvas){const box=canvas.getBoundingClientRect();if(box.width<10||box.height<10)return null;const ratio=Math.min(2,window.devicePixelRatio||1),w=Math.round(box.width*ratio),h=Math.round(box.height*ratio);if(canvas.width!==w||canvas.height!==h){canvas.width=w;canvas.height=h;}const ctx=canvas.getContext('2d');ctx.setTransform(ratio,0,0,ratio,0,0);return {ctx,w:box.width,h:box.height};}
function grid(ctx,w,h,pad){ctx.strokeStyle='#6a97a81a';ctx.lineWidth=1;ctx.font='9px DM Mono,monospace';ctx.fillStyle='#6f919a';for(let i=0;i<5;i++){const y=pad+i*(h-pad*2)/4;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-pad,y);ctx.stroke();}}

function sampleRows(rows,max){if(rows.length<=max)return rows;const stride=(rows.length-1)/(max-1);return Array.from({length:max},(_,i)=>rows[Math.round(i*stride)]);}
function chartData(d){const market=d?.market||{};if(S.mode==='replay'&&S.replayTrades)return sampleRows(S.replayTrades.filter(x=>x&&Number.isFinite(Number(x.price))),120);if(S.priceMode==='candles')return asArray(market.candles).filter(x=>x&&Number.isFinite(Number(x.close))).slice(-70);return asArray(market.trades).filter(x=>x&&Number.isFinite(Number(x.price))).slice(-100);}
function renderPrice(d,force=false){
  const rows=chartData(d),last=rows.at(-1),mode=S.mode==='replay'&&S.replayTrades?'trades':S.priceMode,signature=`${mode}:${rows.length}:${first(last?.id,last?.time,last?.close)}:${first(last?.price,last?.close)}`;
  if(!force&&signature===S.priceSignature)return;S.priceSignature=signature;
  const target=canvasContext($('price-chart'));if(!target)return;const {ctx,w,h}=target;ctx.clearRect(0,0,w,h);grid(ctx,w,h,22);
  $('price-empty').hidden=rows.length<2?false:true;
  if(rows.length<2){text('price-range',rows.length===1?'只有 1 个真实价格点，等待第二笔':'尚无可绘制价格区间');return;}
  const lo=Math.min(...rows.map(r=>mode==='candles'?Number(r.low):Number(r.price)));
  const hi=Math.max(...rows.map(r=>mode==='candles'?Number(r.high):Number(r.price)));
  const padValue=Math.max((hi-lo)*.16,1);const min=lo-padValue,max=hi+padValue;
  const L=45,R=15,T=18,B=27,plotW=w-L-R,plotH=h-T-B;
  const y=value=>T+(max-Number(value))/(max-min)*plotH;
  const t0=Number(rows[0].time),t1=Math.max(t0+1,Number(rows.at(-1).time));
  const xTime=value=>L+(Number(value)-t0)/(t1-t0)*plotW;
  ctx.fillStyle='#b2d5dc';ctx.font='10px DM Mono,monospace';for(let i=0;i<5;i++){const price=max-(max-min)*i/4;ctx.fillText(number(price,0),3,T+i*plotH/4+3)}
  if(mode==='trades'){
    ctx.beginPath();rows.forEach((row,i)=>{const x=xTime(row.time),y0=y(row.price);i?ctx.lineTo(x,y0):ctx.moveTo(x,y0)});
    const gradient=ctx.createLinearGradient(0,T,0,h-B);gradient.addColorStop(0,'#70e6cc3d');gradient.addColorStop(1,'#70e6cc00');
    ctx.lineTo(xTime(rows.at(-1).time),h-B);ctx.lineTo(xTime(rows[0].time),h-B);ctx.closePath();ctx.fillStyle=gradient;ctx.fill();
    ctx.beginPath();rows.forEach((row,i)=>i?ctx.lineTo(xTime(row.time),y(row.price)):ctx.moveTo(xTime(row.time),y(row.price)));
    ctx.strokeStyle='#a8ffe8';ctx.lineWidth=2.6;ctx.shadowColor='#69ffdf';ctx.shadowBlur=14;ctx.stroke();ctx.shadowBlur=0;
    const px=xTime(rows.at(-1).time),py=y(rows.at(-1).price);ctx.beginPath();ctx.arc(px,py,4.8,0,Math.PI*2);ctx.fillStyle='#effff9';ctx.shadowColor='#a8ffe8';ctx.shadowBlur=15;ctx.fill();ctx.shadowBlur=0;
  }else{
    const dx=Math.max(2,Math.min(9,plotW/rows.length*.62));
    rows.forEach(row=>{const x=xTime(row.time),up=Number(row.close)>=Number(row.open),color=up?'#68dec0':'#f38b99';ctx.strokeStyle=color;ctx.fillStyle=color;ctx.globalAlpha=row.complete===false?.38:1;ctx.beginPath();ctx.moveTo(x,y(row.high));ctx.lineTo(x,y(row.low));ctx.stroke();const top=y(Math.max(row.open,row.close)),bot=y(Math.min(row.open,row.close));ctx.fillRect(x-dx/2,top,dx,Math.max(1,bot-top));ctx.globalAlpha=1;});
  }
  const selected=S.mode==='replay'?S.selectedRound:currentLatest(d);
  const stamp=Number(first(selected?.start,selected?.round_id));
  if(Number.isFinite(stamp)&&stamp>=t0&&stamp<=t1){const x=xTime(stamp);ctx.fillStyle='#c9af7550';ctx.fillRect(x-5,T,10,plotH);ctx.strokeStyle='#e0c889';ctx.setLineDash([3,4]);ctx.beginPath();ctx.moveTo(x,T);ctx.lineTo(x,T+plotH);ctx.stroke();ctx.setLineDash([]);ctx.fillStyle='#e5cd91';ctx.fillText('ROUND',Math.min(w-52,x+5),T+11);}
  ctx.fillStyle='#a5c7cd';ctx.font='9px DM Mono,monospace';ctx.fillText(time(t0),L,h-7);ctx.fillText(time(t1),Math.max(L,w-70),h-7);
  text('price-range',`${time(t0)} — ${time(t1)} · ${rows.length} 个${S.mode==='replay'&&S.replayTrades?'过去保存的': '真实'}${mode==='candles'?'每分钟价格':'成交价格'}`);
}

function renderTop(d){const market=d.market||{},health=d.health||{},ticker=market.ticker||{},source=market.source_age_s||{};
  const trades=asArray(market.trades),last=trades.at(-1),lastPrice=first(last?.price,ticker.last,d.signal?.latest?.features?.price);
  text('last-price',money(lastPrice));text('quote-change',market.ready===false?'等待公开行情':'最近成交价 / USD');
  const feed=first(health.feed_age_s,source.trades),trade=first(health.trade_age_s,market.last_trade_age_s,last?.time?d.server_time-last.time:null),book=first(health.book_age_s,source.book);
  text('feed-age',age(feed));text('trade-age',age(trade));text('book-age',age(book));
  text('feed-note',health.paused_reason?reasonLabel(health.paused_reason):market.source_errors?.trades?'读取真实成交失败':'交易所公开信息');text('trade-note',Number(trade)>5?'暂时没有新成交':'交易所真实成交');text('book-note',market.source_errors?.book?'读取买卖报价失败':'交易所买卖报价');
  for(const [id,val,limit] of [['feed-age',feed,7],['trade-age',trade,10],['book-age',book,8]])$(id).closest('.status-stat').classList.toggle('stale',val==null||!Number.isFinite(Number(val))||Number(val)>limit);
  const bad=Boolean(health.paused_reason||market.ready===false||Number(feed)>10),warn=Number(feed)>5||Number(book)>8;
  freshClass($('source-pill'),warn,bad);text('source-status',bad?'行情异常 · 暂停模拟买卖':warn?'行情更新变慢':'真实行情已连接');
  text('model-status',({online:'在线',warming:'准备中',error:'回答失败'})[health.model_status]||health.model_status||'等待本机运行');text('model-note',health.model_error?'这轮回答出错，可点开记录':'Laya 在这台电脑上运行');
  $('chart-live-badge').classList.toggle('stale',bad||Number(trade)>10);text('chart-live-badge',bad?'● 行情太旧':'● 真实行情');
  const bids=asArray(market.bids),asks=asArray(market.asks),bid=Number(bids[0]?.[0]??ticker.bid),ask=Number(asks[0]?.[0]??ticker.ask);
  text('bid-ask',Number.isFinite(bid)&&Number.isFinite(ask)?`${number(bid,0)} / ${number(ask,0)}`:'—');
  const mid=(bid+ask)/2;const spread=Number.isFinite(mid)&&mid>0?(ask-bid)/mid*10000:market.features?.spread_bps;
  text('spread-bps',Number.isFinite(spread)?`${number(spread/100,3)}%`:'—');
  const features=market.features||{};text('buy-share',Number.isFinite(Number(features.taker_buy_share_90s))?`${number(Number(features.taker_buy_share_90s)*100,1)}%`:'—');
  text('imbalance',Number.isFinite(Number(features.book_imbalance))?`${number(Number(features.book_imbalance)*100,1)}%`:'—');
}

function renderSignal(d){const signal=d.signal||{},row=S.mode==='replay'&&S.selectedRound?S.selectedRound:currentLatest(d),rounds=S.mode==='replay'&&row?asArray(signal.rounds).filter(item=>item.manifest_hash===row.manifest_hash):currentRounds(d);
  const b=row?.baseline,o=row?.optimized||{},raw=o.raw||{};
  text('signal-ledger-time',row?.start?time(row.start):'等待本版信号');
  const j=row?.jev,jevChoice=j?.choice?`${dir(j.choice)}${j.status==='late'?' · 迟到，不计分':''}`:j?.status==='error'?'调用失败':d.jev_comparison?.disabled_reason?'本题未调用':'等待 Jev';
  text('ledger-jev',jevChoice);text('jev-current-choice',jevChoice);
  text('jev-current-latency',j?`云端 ${number(j.latency_ms,1)} 毫秒 · ${j.status==='on_time'?'按时保存':j.status==='late'?'迟到':`HTTP ${j.http_status??'未返回'}`}`:d.jev_comparison?.disabled_reason||'等待本题实际返回');

  text('ledger-v0',dir(b?.choice));text('ledger-v2',dir(o?.choice));text('ledger-truth',row?.truth?dir(row.truth):row?.status==='locked'?'等真实价格':row?statusLabel(row.status):'等结果');
  text('base-choice',b?.choice?`${dir(b.choice)} · ${statusLabel(row.status)}`:'等待本版新轮次');
  text('opt-choice',o?.choice?`${dir(o.choice)} · ${statusLabel(row.status)}`:'等待本版新轮次');
  text('base-latency',Number.isFinite(Number(modelMs(b)))?`Laya 用了 ${number(modelMs(b),1)} 毫秒`:'这一版还没有回答');
  text('opt-route',row?`${o.route==='15s_momentum_rule'?'这次用了固定规则':o.route==='laya'?'这次问了本机 Laya':'正在选方法'}${Number.isFinite(Number(modelMs(o)))?` · ${number(modelMs(o),1)} 毫秒`:''}`:'等待选方法');
  text('signal-truth',row?.truth?`${dir(row.truth)}${Number.isFinite(Number(row.move_bps))?` · 实际变动 ${number(row.move_bps/100,3)}%`:''}`:row?.status==='locked'?'等真实价格':row?statusLabel(row.status):'等待新一题');
  const metrics=signal.metrics||{},paired=first(metrics.paired_coverage,signal.paired_coverage);
  const roundsTotal=first(metrics.rounds,signal.round_count);
  const pairedCount=first(metrics.paired,signal.paired_count);
  const historical=S.mode==='replay'&&row?.manifest_hash&&row.manifest_hash!==activeHash(d);
  text('signal-coverage',historical?'过去的一版':!row&&!rounds.length?'等待新题':pairedCount!=null&&roundsTotal!=null?`${pairedCount} / ${roundsTotal}`:fraction(paired)!=null?`${number(fraction(paired)*100,1)}%`:'等待新题');
  text('selected-round',S.mode==='replay'&&S.selectedRound?time(first(S.selectedRound.start,S.selectedRound.round_id)):row?.start?time(row.start):'等待本版');
  $('open-latest-round').disabled=!row;S.latestRound=row||null;
  const validMoves=rounds.filter(r=>r.status==='settled'&&Number.isFinite(Number(r.move_bps))).map(r=>Math.abs(Number(r.move_bps))).sort((a,b)=>a-b);
  const median=validMoves.length?validMoves[Math.floor((validMoves.length-1)/2)]:null;
  const fee=Number(first(d.portfolio?.stats?.cost_bps_one_way,d.portfolio?.fee_bps,d.portfolio?.config?.fee_bps,80));const roundtrip=fee*2;
  text('roundtrip-fee',Number.isFinite(roundtrip)?`至少 ${number(roundtrip/100,2)}%`:'—');text('median-move',median==null?'待积累':`${number(median/100,3)}%`);
  $('cost-fee-bar').style.width=Number.isFinite(roundtrip)?'100%':'0%';$('cost-move-bar').style.width=median!=null&&roundtrip>0?`${Math.max(2,Math.min(100,median/roundtrip*100))}%`:'0%';
  text('cost-note',median==null?'这里按低交易量账户估算费用；实际买卖还可能因报价差而更贵。猜对方向不等于赚钱。':`已揭晓的 ${validMoves.length} 题，5 秒价格变化通常约为图上的数字；费用估算还没有加进所有可能的成交偏差。`);
  renderSignalTimeline(d,row);
}

function renderSignalTimeline(d,row){
  const kinds=new Set(['snapshot_frozen','baseline_model_done','candidate_model_done','optimized_raw','decision_locked','signal_pool','settled','tie','void','model_error','missed']);
  const selected=S.mode==='replay'&&S.selectedRound?S.selectedRound:null;
  const source=selected&&Array.isArray(selected.events)?selected.events:d.events;
  const key=selected?Number(roundId(selected)):null;
  const liveIds=new Set(currentRounds(d).map(item=>String(roundId(item))));
  const events=asArray(source).filter(e=>kinds.has(e.kind)&&(selected?Number(eventRound(e))===key:liveIds.has(String(eventRound(e))))).slice(-5).reverse();
  const lock=row?.status==='locked'||row?.status==='settled'||row?.status==='tie'||row?.status==='void';
  text('signal-lock-state',row?`${time(first(row.start,row.round_id))} · ${lock?'已锁定':statusLabel(row.status)}`:'等待本版新轮次');
  $('signal-timeline-grid').innerHTML=events.length?events.map(e=>{
    const latency=Number(first(e.model_ms,e.elapsed_ms,e.raw?.model_ms));
    const detail=Number.isFinite(latency)?`${number(latency,1)} 毫秒`:e.seq!=null?`记录 #${esc(e.seq)}`:'已保存';
    const lane=e.kind==='baseline_model_done'?'base':e.kind==='candidate_model_done'||e.kind==='optimized_raw'?'opt':'';
    return `<div class="signal-timeline-item ${lane}" title="${esc(eventNames[e.kind]||e.kind)} · ${esc(time(e.time))}"><time>${esc(time(e.time))}</time><strong>${esc(eventNames[e.kind]||e.kind)}</strong><span>${detail}</span></div>`;
  }).join(''):'<span class="signal-timeline-empty">等待本版真实模型与轮次事件…</span>';
}

function accountValue(d,key){const p=d.portfolio||{};return first(p.accounts?.[key],p[key]);}
function renderAccount(d,key,prefix){const p=d.portfolio||{},a=accountValue(d,key),capital=Number(first(p.initial_capital,p.capital,p.config?.capital,10000));
  text(`${prefix}-equity`,a?money(first(a.equity,a.net_asset_value)):'—');
  const eq=Number(first(a?.equity,a?.net_asset_value));const gain=a&&Number.isFinite(eq)&&capital>0?(eq/capital-1)*100:null;
  text(`${prefix}-return`,gain==null?'—':signed(gain));const el=$(`${prefix}-return`);el.classList.toggle('positive',gain>0);el.classList.toggle('negative',gain<0);
  text(`${prefix}-cash`,a?money(a.cash):'—');text(`${prefix}-btc`,a?number(a.btc,6):'—');text(`${prefix}-trades`,a?`${first(a.trades,a.fill_count,0)} 笔`:'—');
  text(`${prefix}-fees`,a?money(first(a.fees,a.fee_usd,0)):'—');
}

function latestActivity(d){const p=d.portfolio||{},orders=asArray(p.orders),evaluations=asArray(p.evaluations);
  const rows=[...orders,...evaluations];return rows.length?rows.sort((a,b)=>Number(first(b.time,b.created_at,b.at,0))-Number(first(a.time,a.created_at,a.at,0)))[0]:null;
}
function renderPolicy(d){const p=d.portfolio||{},e=d.evolution||{},action=latestActivity(d);
  text('explore-version',`虚拟账户使用已登记的规则 · 尚未证明能赚钱`);
  const qualified=asArray(e.qualified_policy)[0],shadow=e.shadow||{},shadowWord=first(qualified?.status,shadow.status,shadow.state,shadow.phase);
  text('shadow-status',shadowWord?`${statusLabel(shadowWord)}${qualified?.reason?` · ${reasonLabel(qualified.reason)}`:''} / 不碰当前账户`:'新方法等未来结果，不碰当前账户');
  const evaluation=action?.baseline||action?.optimized;
  text('latest-action',action?.order_id?`${action.account==='optimized'?'绿色':'蓝色'}账户 ${statusLabel(action.status)}${action.reason?` · ${reasonLabel(action.reason)}`:''}`:evaluation?`蓝色 ${statusLabel(action.baseline?.side)} / 绿色 ${statusLabel(action.optimized?.side)}`:'还没有账户检查');
  text('latest-action-time',action?`${time(first(action.time,action.created_at,action.at))} · ${evaluation?`蓝色：${reasonLabel(evaluation.baseline?.reason)}；绿色：${reasonLabel(evaluation.optimized?.reason)}`:'虚拟账户记录'}`:'等待第一次 30 秒检查');
  renderAccount(d,'baseline','base');renderAccount(d,'optimized','opt');
}

function renderDepth(d){const market=d.market||{},bids=asArray(market.bids),asks=asArray(market.asks),rows=Math.min(10,Math.max(bids.length,asks.length));
  const wrap=$('book-list');if(!rows){wrap.innerHTML='<div class="empty-line">等待有效买卖报价…</div>';return;}
  wrap.innerHTML=Array.from({length:rows},(_,i)=>`<div class="book-row"><span>${bids[i]?number(bids[i][1],5):'—'}</span><span>${bids[i]?money(bids[i][0]):'—'}</span><span>${asks[i]?money(asks[i][0]):'—'}</span><span>${asks[i]?number(asks[i][1],5):'—'}</span></div>`).join('');
  const bidDepth=bids.slice(0,10).reduce((x,r)=>x+Number(r[0])*Number(r[1]),0),askDepth=asks.slice(0,10).reduce((x,r)=>x+Number(r[0])*Number(r[1]),0);
  text('bid-depth',money(bidDepth));text('ask-depth',money(askDepth));
  const bookAge=first(d.health?.book_age_s,market.source_age_s?.book);text('depth-time',Number.isFinite(Number(bookAge))?`买卖报价在 ${age(bookAge)} 前收到`:'等待买卖报价');$('depth-time').classList.toggle('stale',!Number.isFinite(Number(bookAge))||Number(bookAge)>8);
}
function renderTape(d){const market=d.market||{},all=asArray(market.trades),rows=all.slice(-11).reverse(),signature=all.length?`${first(all.at(-1).id,all.at(-1).time)}:${all.at(-1).price}`:'';
  const fresh=S.tapeSignature!==null&&signature&&signature!==S.tapeSignature;S.tapeSignature=signature;
  text('tape-status',rows.length?`${rows.length} 笔展示 · 最后成交 ${age(first(d.health?.trade_age_s,market.last_trade_age_s))} 前`:'无新成交');
  $('tape-list').innerHTML=rows.length?rows.map((r,i)=>`<div class="tape-row ${r.side==='buy'?'buy':'sell'} ${fresh&&i===0?'flash':''}"><span>${time(r.time)}</span><span>${r.side==='buy'?'主动买':'主动卖'}</span><span>${money(r.price)}</span><span>${number(r.volume,6)}</span></div>`).join(''):'<div class="empty-line">等待真实交易所逐笔成交…</div>';
}
function renderHealth(d){const market=d.market||{},health=d.health||{},source=market.source_age_s||{},stats=d.portfolio?.stats||{};
  const rows=[['上次收到成交数据',source.trades,7],['上次真正成交',first(health.trade_age_s,market.last_trade_age_s),10],['上次收到买卖报价',first(health.book_age_s,source.book),8],['买卖报价上次变化',market.book_level_age_s,12],['上次收到分钟价格',source.candles,70],['记录能否保存',health.db_status==='online'||health.db_status==='ok'?0:null,1],['电脑时间正常吗',health.clock_status==='ok'?0:null,1]];
  $('health-grid').innerHTML=rows.map(([label,value,limit])=>{const bad=value==null||!Number.isFinite(Number(value))||Number(value)>limit;const status=label==='记录能否保存'?statusLabel(health.db_status):label==='电脑时间正常吗'?statusLabel(health.clock_status):age(value);return `<div class="health-item ${bad?'bad':''}"><span>${esc(label)}</span><strong>${esc(status)}</strong></div>`}).join('')+`<div class="health-item ${stats.depth_probe_2s_rate==null?'bad':''}"><span>决定后及时收到新报价</span><strong>${stats.depth_probe_2s_rate==null?'待测':`${number(fraction(stats.depth_probe_2s_rate)*100,1)}% / ${first(stats.depth_probe_slots,0)} 次`}</strong></div>`;
  text('health-status',health.paused_reason?`暂停模拟买卖：${reasonLabel(health.paused_reason)}`:'逐项检查真实数据');
  const evals=asArray(d.portfolio?.evaluations),counts=new Map();for(const r of evals)for(const lane of ['baseline','optimized']){const reason=reasonLabel(first(r[lane]?.reason,r.reason,r.status,'未知'));counts.set(reason,(counts.get(reason)||0)+1)}
  text('evaluation-count',`${evals.length} 次`);
  if(!counts.size){$('block-bars').innerHTML='<span>等待真实评估…</span>';return;}
  const top=[...counts].sort((a,b)=>b[1]-a[1]).slice(0,5),max=top[0][1];$('block-bars').innerHTML=top.map(([name,count])=>`<div title="${esc(name)}：${count} 次"><strong>${count}</strong><i style="height:${Math.max(8,count/max*57)}px"></i><small>${esc(name)}</small></div>`).join('');
}

function drawEquity(d){const points=asArray(S.mode==='replay'&&S.replayPoints?S.replayPoints:d.portfolio?.points).filter(r=>Number.isFinite(Number(r.time))&&Number.isFinite(Number(r.baseline))&&Number.isFinite(Number(r.optimized)));
  const z=canvasContext($('equity-chart'));if(!z)return;const {ctx,w,h}=z;ctx.clearRect(0,0,w,h);grid(ctx,w,h,19);
  $('equity-empty').hidden=points.length>=2;
  if(points.length<2){S.equityScale=null;return;}
  const fields=[['cash','#7c909d',1.1],['buy_hold','#e5c679',1.5],['baseline','#72c7ff',2.0],['optimized','#75efca',2.4]];
  const all=points.flatMap(r=>fields.map(([key])=>Number(r[key])).filter(Number.isFinite));if(!all.length)return;
  let min=Math.min(...all),max=Math.max(...all);const cap=Number(first(d.portfolio?.initial_capital,d.portfolio?.capital,d.portfolio?.config?.capital,10000));const pad=Math.max((max-min)*.18,cap*.00025);min-=pad;max+=pad;
  const L=54,R=18,T=17,B=28,t0=Number(points[0].time),t1=Math.max(t0+1,Number(points.at(-1).time)),x=r=>L+(Number(r.time)-t0)/(t1-t0)*(w-L-R),y=v=>T+(max-Number(v))/(max-min)*(h-T-B);
  ctx.font='9px DM Mono,monospace';ctx.fillStyle='#77949c';for(let i=0;i<5;i++){const v=max-(max-min)*i/4;ctx.fillText(number(v,0),2,T+i*(h-T-B)/4+3)}
  for(const [key,color,width] of fields){if(!points.some(r=>Number.isFinite(Number(r[key]))))continue;ctx.beginPath();let begun=false;for(const row of points){const v=Number(row[key]);if(!Number.isFinite(v))continue;begun?ctx.lineTo(x(row),y(v)):ctx.moveTo(x(row),y(v));begun=true}ctx.strokeStyle=color;ctx.lineWidth=width;ctx.shadowColor=color;ctx.shadowBlur=key==='optimized'?7:0;ctx.stroke();ctx.shadowBlur=0;}
  const hover=S.chartHover;if(hover!=null&&hover>=L&&hover<=w-R){const target=t0+(hover-L)/(w-L-R)*(t1-t0),row=points.reduce((best,next)=>Math.abs(Number(next.time)-target)<Math.abs(Number(best.time)-target)?next:best);const xx=x(row);ctx.strokeStyle='#d7f4e699';ctx.setLineDash([3,5]);ctx.beginPath();ctx.moveTo(xx,T);ctx.lineTo(xx,h-B);ctx.stroke();ctx.setLineDash([]);const tip=$('equity-tooltip');tip.style.display='block';tip.style.left=`${Math.min(w-165,Math.max(60,xx+10))}px`;tip.style.top='20px';tip.innerHTML=`<b>${time(row.time)}</b><span>蓝色 ${money(row.baseline)}</span><span>绿色 ${money(row.optimized)}</span><span>买入后不动 ${money(row.buy_hold)}</span><span>一直拿现金 ${money(row.cash)}</span>`;}else $('equity-tooltip').style.display='none';
  ctx.fillStyle='#76959d';ctx.fillText(time(t0),L,h-6);ctx.fillText(time(t1),Math.max(L,w-70),h-6);
  S.equityScale={points,t0,t1,L,R,w};
}
function renderEquity(d){const p=d.portfolio||{},a=accountValue(d,'baseline'),b=accountValue(d,'optimized');const va=Number(a?.equity),vb=Number(b?.equity),diff=a&&b&&Number.isFinite(va)&&Number.isFinite(vb)?vb-va:null;
  text('equity-gap',diff==null?'—':money(diff));$('equity-gap').classList.toggle('stale-text',diff!=null&&diff<0);
  text('mark-time',p.mark_time?time(p.mark_time):p.points?.length?time(p.points.at(-1).time):'等待估值');
  const firstMark=first(p.started_at,asArray(p.points)[0]?.time);text('equity-foot',`两个虚拟账户从同一时间 ${firstMark?dateTime(firstMark):'待登记'} 出发 · 已扣模拟费用 · 没有混入早先实验`);
  drawEquity(d);
}
function renderOrders(d){const p=d.portfolio||{},rows=asArray(S.mode==='replay'&&S.replayOrders?S.replayOrders:p.orders).slice(0,12);text('order-count',`${rows.length} 条记录`);
  $('order-list').innerHTML=rows.length?rows.map(row=>{const fill=row.fill||{},intent=row.intent||{},status=statusLabel(first(row.status,row.result,row.action)),account=row.account==='optimized'?'绿色 · 先选方法':'蓝色 · 直接问 Laya',at=first(row.time,row.created_at,row.at),price=first(fill.simulated_fill_price,fill.price,row.fill_price,row.price),quote=first(fill.quote_price,fill.best_ask,fill.best_bid),qty=first(fill.quantity_btc,intent.quantity_btc),fee=first(fill.fee_usd,row.fee_usd),quotedAt=first(fill.quote_received_at,fill.executed_at),reason=reasonLabel(first(row.reason,fill.reason,intent.reason));const tone=['blocked','timeout','unfilled'].includes(row.status)?'blocked':'';return `<div class="order-item"><div><strong>${esc(account)} · ${esc(status)}</strong><span class="status ${tone}">${esc(time(at))}</span></div><div class="order-trace"><span>先决定 ${esc(time(at))}</span><i>→</i><span>收到新报价 ${esc(time(quotedAt))}</span><i>→</i><span>记入虚拟账户 ${row.status==='filled'?esc(time(fill.executed_at)):'没有成交'}</span></div><small>${esc(reason)} · ${esc(row.side==='buy'?'买入':'卖出')} · 新报价 ${esc(money(quote))} · 模拟成交价 ${esc(money(price))} · 数量 ${esc(number(qty,6))} BTC · 费用 ${esc(money(fee))}</small></div>`}).join(''):'<div class="empty-line">目前没有模拟买卖。两种方法仍在猜涨跌，虚拟账户如实显示零成交。</div>';
}
function renderResearch(d){const evolution=d.evolution||{},manifest=evolution.active_manifest||{},candidates=asArray(evolution.candidates);
  text('version-hash',manifest.hash?'规则已记录':'等待记录规则');
  const facts=[['当前使用',manifest.hash?'已固定的规则':'等待规则'],['负责快速判断','这台电脑上的 Laya'],['ChatGPT 的参与',evolution.teacher_mode==='online'?'在线服务已配置':'参与离线设计'],['新方法能否启用',evolution.shadow?.trade_qualified?'已达到预设测试条件':'未来测试还不够']];
  const technical=[['规则原名',first(manifest.spec?.name,manifest.version,manifest.name,'—')],['原始编号',manifest.hash||'—'],['模型原名',first(manifest.spec?.model,'—')]];
  $('manifest').innerHTML=facts.map(([key,val])=>`<div class="manifest-row"><span>${esc(key)}</span><strong>${esc(val)}</strong></div>`).join('')+`<details class="manifest-technical"><summary>查看原始版本信息</summary>${technical.map(([key,val])=>`<div class="manifest-row"><span>${esc(key)}</span><strong title="${esc(val)}">${esc(val)}</strong></div>`).join('')}</details>`;
  text('candidate-count',`${candidates.length} 个待测方案`);
  $('candidate-list').innerHTML=candidates.length?candidates.slice(0,6).map((c,i)=>`<div class="candidate"><strong>待测方法 ${i+1} · ${esc(statusLabel(first(c.status,c.state)))}</strong><span>提出于 ${esc(c.created_at?dateTime(c.created_at):'—')} · 从 ${esc(c.forward_start?dateTime(c.forward_start):'—')} 开始接受新题</span><details><summary>看原始编号</summary>${esc(first(c.candidate_id,c.name,c.version,c.spec_hash,'—'))}</details></div>`).join(''):'<div class="empty-line">目前没有待测的新方案，不会编造“优化成功”。</div>';
  const shadow=evolution.shadow||{},qualified=asArray(evolution.qualified_policy)[0];text('shadow-state',qualified?`最近一次新方法检查：${statusLabel(qualified.status)} · ${reasonLabel(qualified.reason)}。这不改变当前两个虚拟账户。`:shadow.status?`新方法仍在测试：${statusLabel(shadow.status)}。${shadow.reason?reasonLabel(shadow.reason):'未来结果还不够，不改变当前账户。'}`:'新方法要积累足够长时间的真实结果；当前没有证明它能带来交易收益。');
}
const eventNames={poll_heartbeat:'收到行情回复',new_trade_received:'出现一笔真实成交',snapshot_frozen:'记下答题前的信息',baseline_model_done:'蓝色方法已回答',candidate_model_done:'绿色方法已回答',optimized_raw:'绿色方法已回答',decision_locked:'两边答案已提交',signal_pool:'等待价格揭晓',settled:'真实结果已揭晓',tie:'这题涨跌打平',void:'这题数据不够',portfolio_evaluation:'检查一次虚拟账户',qualified_policy_evaluation:'检查待测新方法',order_intent:'准备模拟买卖',gate_pass:'通过安全检查',blocked:'安全或费用不合适',paper_fill:'虚拟账户记入买卖',timeout:'等新报价超时',depth_probe:'检查新买卖报价',account_mark:'虚拟账户金额更新',mark_stale:'账户金额暂时过旧',candidate_frozen:'固定一套待测方法',shadow_candidate_decision:'新方法旁观作答',candidate_forward_complete:'新方法完成一段未来测试',model_error:'Laya 回答失败',missed:'这题没赶上截止',source_gap:'交易所数据有缺口',engine_error:'系统暂停'};
window.btcEventNames=eventNames;
function renderAudit(d){const events=asArray(d.events).filter(e=>e.kind!=='poll_heartbeat').slice(-9).reverse();$('audit-events').innerHTML=events.length?events.map(e=>{const key=eventRound(e),tone=e.kind==='baseline_model_done'?'base':e.kind==='candidate_model_done'?'opt':'';return `<div class="audit-event ${tone}" ${key!=null?`data-round="${esc(key)}"`:''}><time>${time(e.time)}</time><strong>${esc(eventNames[e.kind]||e.kind)}</strong><span>${key!=null?`#${esc(key)}`:'系统'}</span></div>`}).join(''):'<div class="empty-line">等待真实事件…</div>';
}

function renderPerformance(d){
  const m=d.signal?.metrics||{},b=m.baseline||{},o=m.optimized||{},eligible=Number(first(m.primary_labels,b.eligible,o.eligible,0));
  const bRate=fraction(b.accuracy),oRate=fraction(o.accuracy),comparable=eligible>0&&bRate!=null&&oRate!=null;
  text('score-scope','从这版开始累计 · 只比较双方都答了、真实结果也清楚的题');
  text('score-v0',comparable?`${number(bRate*100,1)}%`:'—');
  text('score-v2',comparable?`${number(oRate*100,1)}%`:'—');
  text('score-v0-detail',comparable?`${number(b.eligible,0)} 题中猜对 ${number(b.wins,0)} 题`:'等待能核对结果的题');
  text('score-v2-detail',comparable?`${number(o.eligible,0)} 题中猜对 ${number(o.wins,0)} 题`:'等待能核对结果的题');
  $('score-v0-bar').style.width=comparable?`${Math.max(0,Math.min(100,bRate*100))}%`:'0%';
  $('score-v2-bar').style.width=comparable?`${Math.max(0,Math.min(100,oRate*100))}%`:'0%';
  const edge=comparable?(oRate-bRate)*100:null;
  $('score-edge').innerHTML=edge==null?'—':`${edge>0?'+':''}${number(edge,1)}<small>个百分点</small>`;
  text('score-edge-detail',edge==null?'等待能核对结果的同一批题':edge>0?'绿色方法这批题猜对得更多':edge<0?'蓝色方法这批题猜对得更多':'两边这批题猜对率相同');
  text('score-paired',`两边都及时回答 ${number(first(m.post_warmup_paired,m.paired,0),0)} 题`);
  text('score-primary',`结果清楚 ${number(eligible,0)} 题`);
  text('score-coverage',m.post_warmup_paired_coverage!=null?`两边都及时回答的比例 ${number(fraction(m.post_warmup_paired_coverage)*100,1)}%`:'双方作答情况待积累');
  const stats=d.portfolio?.stats||{},probeSlots=Number(first(stats.depth_probe_slots,0)),probeRate=fraction(stats.depth_probe_2s_rate);
  text('score-probe',probeSlots&&probeRate!=null?`决定后及时收到新报价：${number(probeRate*100,1)}% / ${number(probeSlots,0)} 次检查`:'新报价是否来得及：待积累');
  const candidates=asArray(d.evolution?.candidates),candidate=candidates.at(-1),progress=candidate?.progress||{};
  text('score-shadow',candidate?`新方法已做 ${number(first(progress.valid_labels,0),0)} / ${number(first(progress.required_valid,5000),0)} 道未来题 · 仍在测试`:'目前没有待测的新方法');
  const accounts=d.portfolio?.accounts||{},base=accounts.baseline,opt=accounts.optimized;
  const bPnl=Number(base?.pnl),oPnl=Number(opt?.pnl),haveAccounts=Number.isFinite(bPnl)&&Number.isFinite(oPnl);
  text('score-v0-pnl',haveAccounts?money(bPnl):'—');text('score-v2-pnl',haveAccounts?money(oPnl):'—');
  text('score-capital-gap',haveAccounts?money(Math.abs(oPnl-bPnl)):'—');
  let capitalCaption='等待两个模拟账户更新金额';
  if(haveAccounts){const gap=oPnl-bPnl,leader=gap>0?'绿色账户目前更多':gap<0?'蓝色账户目前更多':'两边账户目前一样',profit=bPnl<0&&oPnl<0?' · 两边目前都亏':bPnl>0&&oPnl>0?' · 两边目前都赚':'';capitalCaption=`${leader}${profit} · ${base?.mark_stale||opt?.mark_stale?'金额更新可能滞后':'已按当前价格计算'}`;}
  text('score-capital-caption',capitalCaption);
  text('score-fills',stats.fills!=null?`${number(stats.fills,0)} 笔`:'—');
  text('score-fees',base?.fees!=null&&opt?.fees!=null?`${money(base.fees)} / ${money(opt.fees)}`:'—');
  text('score-drawdown',base?.max_drawdown!=null&&opt?.max_drawdown!=null?`${signed(Number(base.max_drawdown)*100,2)} / ${signed(Number(opt.max_drawdown)*100,2)}`:'—');
  const latest=currentLatest(d),bMs=modelMs(latest?.baseline),oMs=modelMs(latest?.optimized);
  text('score-latency',bMs!=null&&oMs!=null?`${number(bMs,1)} / ${number(oMs,1)} 毫秒`:'等待本机回答');
}

function renderNetwork(d){
  BtcNetwork.render(S.mode==='replay'&&S.selectedRound?{...d,network_round:S.selectedRound,signal:{...d.signal,rounds:[S.selectedRound]}}:d);
  text('network-kicker',S.mode==='replay'?'REPLAY / 过去保存的真实决策':'LIVE / 真实价格带动的决策地图');text('network-live-text',S.mode==='replay'?'回看已保存的记录':'有新记录才亮起');
  const market=d.market||{},last=asArray(market.trades).at(-1),price=first(last?.price,market.ticker?.last);
  text('network-price',S.mode==='replay'?`回看 · ${time(S.selectedRound?.start)}`:price!=null?`BTC / USD $${number(price,2)}`:'BTC / USD —');
  const recent=asArray(d.events).filter(e=>e.kind!=='poll_heartbeat').at(-1);
  text('network-last-event',S.mode==='replay'?`${dateTime(S.selectedRound?.start)} · 过去保存的真实题目`:recent?`${time(recent.time)} · ${eventNames[recent.kind]||'新事件'}`:'等待本机事件');
}

function flash(id){const node=$(id);if(!node)return;node.classList.remove('active');void node.getBoundingClientRect();node.classList.add('active');setTimeout(()=>node.classList.remove('active'),1050);}
function animateEvent(event){
  BtcNetwork.animate(event);
  switch(event.kind){
    case 'new_trade_received':flash('source-pill');break;
    case 'portfolio_evaluation':flash('countdown-30');break;
    case 'blocked':case 'timeout':flash('latest-action');break;
    case 'paper_fill':flash(event.account==='optimized'?'opt-equity':'base-equity');break;
    case 'account_mark':flash('equity-gap');break;
    default:break;
  }
}
function ingestEvents(d){const events=asArray(d.events).filter(e=>Number.isFinite(Number(e.seq))).sort((a,b)=>Number(a.seq)-Number(b.seq));if(!events.length)return;
  const newest=Number(events.at(-1).seq);
  if(S.seenSeq==null){S.seenSeq=newest;return;}
  if(newest<S.seenSeq){S.seenSeq=newest;text('health-status','事件序号重启 · 旧动画已清空');return;}
  const incoming=events.filter(e=>Number(e.seq)>S.seenSeq);
  if(incoming.length&&Number(incoming[0].seq)>S.seenSeq+1)text('health-status',`事件缺口 ${S.seenSeq+1}–${Number(incoming[0].seq)-1} · 未补动画`);
  for(const event of incoming)animateEvent(event);S.seenSeq=newest;
}

function renderJev(d){
  const row=S.mode==='replay'&&S.selectedRound?S.selectedRound:currentLatest(d),comparison=d.jev_comparison||{},jev=row?.jev;
  text('tri-blue-choice',row?.baseline?.choice?dir(row.baseline.choice):'等待新题');
  text('tri-green-choice',row?.optimized?.choice?dir(row.optimized.choice):'等待新题');
  text('tri-jev-choice',jev?.status==='on_time'?dir(jev.choice):jev?.status==='late'?'迟到，不计分':jev?.status==='error'?'调用失败':comparison.disabled_reason?'本题未调用':'等待 Jev');
  text('tri-truth',row?.truth?dir(row.truth):'等待揭晓');
  for(const [key,id] of [['baseline','tri-blue-score'],['optimized','tri-green-score'],['jev','tri-jev-score']]){
    const n=Number(comparison.shared_primary||0),wins=Number(comparison.wins?.[key]||0);
    text(id,n?`同题 ${wins} / ${n} · ${number(wins/n*100,1)}%`:'同题成绩待积累');
  }
  text('tri-shared-count',`三路有效同题 ${number(comparison.shared_primary||0,0)} 道`);
  const recent=asArray(comparison.recent_scored);
  $('jev-recent').innerHTML=recent.length?recent.map(r=>`<button type="button" class="jev-round" data-round="${esc(r.start)}"><time>${esc(time(r.start))}</time><span>蓝 ${esc(dir(r.baseline))}</span><span>绿 ${esc(dir(r.optimized))}</span><span>紫 ${esc(dir(r.jev))}</span><strong>实际 ${esc(dir(r.truth))}</strong><small>回看证据 ↗</small></button>`).join(''):'<div class="empty-line">等待第一道有效共同题目</div>';
  const latest=comparison.latest||jev;
  const accessError=latest?.http_status===401||latest?.http_status===402||latest?.http_status===403;
  const capped=comparison.max_calls>0&&comparison.calls>=comparison.max_calls&&!!comparison.disabled_reason;
  text('jev-provider-status',capped?'Jev 本次观察已到调用上限':comparison.disabled_reason?'Jev 已暂停':accessError?'Jev 权限待处理':comparison.calls?'Jev 云端接口已调用':'Jev 云端接口等待新题');
  text('jev-latency',latest?.latency_ms!=null?`最近调用 ${number(latest.latency_ms,1)} 毫秒 · ${latest.status==='on_time'?'按时':'未计分'}`:'Jev 调用耗时待记录');
  text('jev-coverage',`已请求 ${number(comparison.calls||0,0)} / ${comparison.unlimited_calls?'不限次数':number(comparison.max_calls||0,0)} · 按时 ${number(comparison.on_time||0,0)} · 迟到 ${number(comparison.late||0,0)} · 错误 ${number(comparison.errors||0,0)}`);
  const err=$('jev-error');err.hidden=capped||(!comparison.disabled_reason&&!accessError);err.textContent=comparison.disabled_reason||(accessError?`HTTP ${latest.http_status}: ${latest.error}`:'');
  if(comparison.unlimited_calls&&!comparison.disabled_reason)text('jev-retry-note','持续处理真实新题；已取消累计调用次数上限。');
  if(capped)text('jev-retry-note','本次调用上限已到；成绩和回看继续保留。蓝绿两路与模拟账户继续运行。');
}
function render(d,force=false){if(!d||typeof d!=='object')return;S.view=d;S.serverOffset=Number(d.dashboard?.served_at||d.server_time||Date.now()/1000)*1000-Date.now();renderTop(d);renderSignal(d);renderPerformance(d);renderJev(d);renderNetwork(d);renderPolicy(d);renderPrice(d,force);renderDepth(d);renderTape(d);renderHealth(d);renderEquity(d);renderOrders(d);renderResearch(d);renderAudit(d);tick();
  const info=d.dashboard||{};text('dashboard-update-note',`状态采集 ${time(d.server_time)} · 累计成绩更新 ${time(info.scores_updated_at||d.server_time)}${info.score_interval_s?'（后台定期更新）':''}${info.last_score_error?` · 成绩更新失败：${info.last_score_error}`:''}`);
  if(info.stale||info.last_error){text('source-status',`状态更新滞后 ${number(info.snapshot_age_s,1)} 秒`);text('health-status',info.last_error?`状态读取错误：${info.last_error}`:'当前显示上次实际状态，等待新记录');freshClass($('source-pill'),true,true);}
}
async function refresh(){if(S.busy)return;S.busy=true;const controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),8000);try{const response=await fetch('/api/btc/state',{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error(response.status===503?'实时状态正在准备':`HTTP ${response.status}`);const d=await response.json();S.live=d;
    if(S.mode==='live'){render(d);ingestEvents(d);}else{S.queued=Math.max(0,Number(first(d.event_seq,asArray(d.events).at(-1)?.seq,0))-Number(S.seenSeq||0));if(S.mode==='paused')text('mode-banner-note',`仅画面暂停，后台仍持续记录；已有 ${S.queued} 个新事件。`);}
  }catch(error){text('source-status','等待状态更新');text('health-status',`更新失败：${String(error.message||error)}`);freshClass($('source-pill'),false,true);}finally{clearTimeout(timeout);S.busy=false;}}
function remaining(now,period){const v=period-now%period;return v===period?0:v;}
function tick(){if(S.mode!=='live'||!S.view)return;const now=(Date.now()+S.serverOffset)/1000;const five=remaining(now,5),thirty=remaining(now,30),fifteen=remaining(now,900),fifteenSeconds=Math.ceil(fifteen);
  text('countdown-5',`${five.toFixed(1)}s`);text('countdown-30',`${Math.ceil(thirty)}s`);text('countdown-15m',`${Math.floor(fifteenSeconds/60)}m ${String(fifteenSeconds%60).padStart(2,'0')}s`);$('tempo-fill').style.width=`${((5-five)/5*100).toFixed(1)}%`;text('footer-clock',new Date(now*1000).toLocaleString('zh-CN',{hour12:false}));}

function findRound(key){const rounds=asArray(S.live?.signal?.rounds),wanted=String(key);return rounds.find(r=>String(roundId(r))===wanted||String(r.start)===wanted)||null;}
function evidenceLine(label,at,detail){return `<div class="drawer-step"><time>${esc(time(at))}</time><strong>${esc(label)}</strong><div>${esc(detail)}</div></div>`;}
function drawDrawerPrice(rows){const canvas=$('drawer-price-chart');if(!canvas)return;const z=canvasContext(canvas);if(!z)return;const {ctx,w,h}=z;ctx.clearRect(0,0,w,h);grid(ctx,w,h,13);const valid=sampleRows(asArray(rows).filter(r=>Number.isFinite(Number(r.price))),90);if(valid.length<2)return;const lo=Math.min(...valid.map(r=>Number(r.price))),hi=Math.max(...valid.map(r=>Number(r.price))),pad=Math.max((hi-lo)*.18,.3),min=lo-pad,max=hi+pad,t0=Number(valid[0].time),t1=Math.max(t0+1,Number(valid.at(-1).time));const x=r=>12+(Number(r.time)-t0)/(t1-t0)*(w-24),y=v=>14+(max-Number(v))/(max-min)*(h-28);ctx.beginPath();valid.forEach((r,i)=>i?ctx.lineTo(x(r),y(r.price)):ctx.moveTo(x(r),y(r.price)));ctx.strokeStyle='#7be7d3';ctx.lineWidth=2;ctx.stroke();const start=Number(S.selectedRound?.start);if(start>=t0&&start<=t1){const xx=12+(start-t0)/(t1-t0)*(w-24);ctx.setLineDash([3,4]);ctx.strokeStyle='#f0ce7e';ctx.beginPath();ctx.moveTo(xx,7);ctx.lineTo(xx,h-7);ctx.stroke();ctx.setLineDash([]);}}
function showDrawer(row){const b=row.baseline||{},o=row.optimized||{},start=first(row.start,row.round_id),m=row.manifest||{},snapshot=row.snapshot||{},features=snapshot.features||{};
  const historical=row.manifest_hash&&row.manifest_hash!==activeHash(S.live);
  text('drawer-title',`${time(start)} 这一题`);text('drawer-subtitle',`${dateTime(start)} · ${statusLabel(row.status)} · ${historical?'当时使用旧规则 · ':''}过去保存的真实记录`);
  const snapshotId=first(row.snapshot_id,row.market_snapshot_id,'—');
  const j=row.jev,shared=j?.status==='on_time'&&j.snapshot_id===row.snapshot_id&&row.locked_at<row.start&&row.label_tier==='primary'&&['higher','lower'].includes(row.truth);
  const jevEvidence=`<div class="drawer-related"><h3>紫色 Jev 的实际记录</h3>${j?`<div class="drawer-kpi"><div><small>Jev 怎么猜</small><strong>${esc(j.choice?dir(j.choice):'调用失败')}</strong></div><div><small>三路同题成绩</small><strong>${shared?'计入三路共同分母':'未计入三路共同分母'}</strong></div></div><p>HTTP ${esc(j.http_status??'未返回')} · ${esc(number(j.latency_ms,1))} 毫秒 · ${j.status==='on_time'?'按时保存':j.status==='late'?'迟到，排除计分':'错误，排除计分'}<br>提交 ${esc(time(j.submitted_at))} → 返回 ${esc(time(j.completed_at))} → 开题 ${esc(time(row.start))}${j.error?`<br>${esc(j.error)}`:''}</p>`:'<p>这题没有调用 Jev；不会补答过去题目。</p>'}<button type="button" class="mode-btn" id="drawer-show-network">在流程图回看这题 ↗</button></div>`;
  const data=`<div class="drawer-kpi"><div><small>蓝色怎么猜</small><strong>${esc(dir(b.choice))}</strong></div><div><small>绿色怎么猜</small><strong>${esc(dir(o.choice))}</strong></div><div><small>真实价格怎么走</small><strong>${esc(row.truth?dir(row.truth):row.status==='locked'?'等真实价格':statusLabel(row.status))}</strong></div><div><small>是否计入成绩</small><strong>${esc(row.status==='locked'?'等结果揭晓':row.label_tier==='primary'?'计入：前后价格都及时':row.label_tier==='reference'?'只作参考：价格稍晚':'不计入主成绩')}</strong></div></div>`;
  const savedEvents=asArray(row.events),steps=savedEvents.length?savedEvents.map(e=>evidenceLine(eventNames[e.kind]||'系统记录',e.time,e.reason?reasonLabel(e.reason):e.choice?dir(e.choice):e.model_ms!=null?`${e.model_ms} 毫秒`:'已保存')).join(''):[evidenceLine('记下答题前的信息',first(row.frozen_at,features.cutoff),`记录编号 ${snapshotId}`),evidenceLine('蓝色方法回答',row.locked_at,`${dir(b.choice)} · 用时 ${number(modelMs(b),1)} 毫秒`),evidenceLine('绿色方法回答',row.locked_at,`${dir(o.choice)} · 本题使用 ${o.route==='laya'?'本机 Laya':'预先写好的规则'}`),evidenceLine('两边答案已提交',row.locked_at,statusLabel(row.status)),evidenceLine('真实价格揭晓',row.end,row.truth?`${dir(row.truth)} · 实际变动 ${number(row.move_bps/100,3)}%`:statusLabel(row.status))].join('');
  const evidence=`<details class="drawer-raw"><summary>查看这题的时间与原始编号</summary><div class="manifest-row"><span>当时信息编号</span><strong title="${esc(snapshotId)}">${esc(String(snapshotId).slice(0,22))}</strong></div><div class="manifest-row"><span>答题前最后成交</span><strong>${esc(time(features.last_trade_time))}</strong></div><div class="manifest-row"><span>答题信息截止</span><strong>${esc(time(snapshot.received_cutoff))}</strong></div><div class="manifest-row"><span>当时看到的成交笔数</span><strong>${esc(number(asArray(snapshot.trade_ids).length,0))}</strong></div><div class="manifest-row"><span>使用的规则编号</span><strong title="${esc(first(row.manifest_hash,m.hash,'—'))}">${esc(String(first(row.manifest_hash,m.hash,'—')).slice(0,22))}</strong></div></details>`;
  const trades=asArray(row.trade_window),evaluation=row.evaluation,linkedOrders=asArray(row.orders);
  const marketWindow=`<div class="drawer-history"><h3>这题前后的真实价格 <small>${trades.length} 笔 · 答题前 60 秒到结束后 10 秒</small></h3>${trades.length>=2?'<canvas id="drawer-price-chart" aria-label="这一题前后的真实成交价格"></canvas>':'<div class="empty-line">保存的真实成交还不够，无法画出这题前后的价格。</div>'}</div>`;
  const evalSummary=evaluation?`<div class="drawer-related"><h3>之后一次虚拟账户检查</h3><p>它会参考之前最多 6 道题，不会因为这一题猜对就立刻买入。</p><div class="drawer-kpi"><div><small>蓝色账户怎么做</small><strong>${esc(statusLabel(evaluation.baseline?.side))}</strong><span>${esc(reasonLabel(evaluation.baseline?.reason))}</span></div><div><small>绿色账户怎么做</small><strong>${esc(statusLabel(evaluation.optimized?.side))}</strong><span>${esc(reasonLabel(evaluation.optimized?.reason))}</span></div></div></div>`:'<div class="drawer-related"><h3>之后的虚拟账户检查</h3><p>还没有找到与这一题关联的记录。</p></div>';
  const orderSummary=linkedOrders.length?`<div class="drawer-related"><h3>虚拟账户有没有买卖</h3>${linkedOrders.map(order=>`<div class="drawer-order"><strong>${esc(order.account==='optimized'?'绿色':'蓝色')} ${esc(statusLabel(order.status))}</strong><span>准备 ${esc(time(order.time))} → 新报价 ${esc(time(first(order.quote_received_at,order.fill?.executed_at)))} → 模拟价格 ${esc(money(order.fill?.simulated_fill_price))} · 费用 ${esc(money(order.fill?.fee_usd))}</span></div>`).join('')}</div>`:'<div class="drawer-related"><h3>虚拟账户有没有买卖</h3><p>没有。这次选择保持现金，或安全检查没有通过。</p></div>';
  $('drawer-body').innerHTML=`${data}${jevEvidence}${marketWindow}<div class="drawer-timeline"><h3>这题先后发生了什么</h3>${steps}</div>${evalSummary}${orderSummary}<p class="drawer-disclosure">每 5 秒只猜一次涨跌，不直接下单。虚拟账户每 30 秒另做一次买卖检查。</p>${evidence}<details class="drawer-raw"><summary>给想深入核对的人：原始数据</summary><pre>${esc(JSON.stringify(row,null,2))}</pre></details>`;
  $('audit-overlay').hidden=false;document.body.style.overflow='hidden';
  if(trades.length>=2)drawDrawerPrice(trades);
}
async function openRound(key){let fallback=findRound(key);
  if(!fallback){try{const response=await fetch(`/api/btc/round?start=${encodeURIComponent(key)}`,{cache:'no-store'});if(response.ok)fallback=(await response.json()).round;}catch(_error){return;}}
  if(!fallback)return;S.selectedRound=fallback;
  const historical=fallback.manifest_hash&&fallback.manifest_hash!==activeHash(S.live);
  setMode('replay',`正在看 ${dateTime(first(fallback.start,fallback.round_id))} 的那一题${historical?' · 当时用的是旧规则':''}。价格图会切换到那时；顶部账户金额仍显示进入回看时的画面。`);
  $('replay-shade').querySelector('small').textContent=`${dateTime(first(fallback.start,fallback.round_id))} · 非实时行情`;
  renderSignal({...S.view,signal:{...(S.view?.signal||{}),latest:fallback}});renderJev(S.view||S.live);renderNetwork(S.view||S.live);renderPrice(S.view||S.live,true);showDrawer(fallback);
  try{const url=`/api/btc/round?start=${encodeURIComponent(first(fallback.start,fallback.round_id))}`;const response=await fetch(url,{cache:'no-store'});if(response.ok){const detail=await response.json();const full={...first(detail.round,detail.row,detail),snapshot:detail.snapshot,events:detail.events,trade_window:detail.trade_window,marks:detail.marks,evaluation:detail.evaluation,orders:detail.orders};S.selectedRound=full;S.replayTrades=asArray(detail.trade_window);S.replayPoints=asArray(detail.marks);S.replayOrders=asArray(detail.orders);S.priceSignature=null;renderSignal({...S.view,signal:{...(S.view?.signal||{}),latest:full}});renderJev(S.view||S.live);renderNetwork(S.view||S.live);renderPrice(S.view||S.live,true);drawEquity(S.view||S.live);renderOrders(S.view||S.live);text('price-cadence','现在看到的是过去保存的真实成交，不是此刻的价格');text('equity-foot','现在只看那题附近保存的账户记录；顶部金额保留进入回看时的画面。');text('equity-empty','那题附近的账户记录还不够，无法画局部曲线');showDrawer(full);}}catch(_error){/* The saved summary still provides a truthful replay. */}
}
function closeDrawer(){ $('audit-overlay').hidden=true;document.body.style.overflow='';setMode('live'); }

$('pause-btn').addEventListener('click',()=>{if(S.mode==='live'){setMode('paused');return;}closeDrawer();});
$('jev-retry').addEventListener('click',async()=>{
  const button=$('jev-retry');button.disabled=true;
  try{
    const response=await fetch('/api/btc/jev/retry',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    if(!response.ok)throw new Error(`HTTP ${response.status}`);
    const result=await response.json();
    const notes={waiting_for_future_snapshot:'已恢复等待：下一道新题会真实调用 Jev。',already_running:'Jev 已在等待或处理新题。',missing_key:'当前服务未读到密钥，请检查私有环境文件。',call_limit:'本次调用上限已到，请先检查额度与用量。',cooldown:`请 ${result.retry_after_s||30} 秒后再检查。`};
    text('jev-retry-note',notes[result.status]||result.status);await refresh();
  }catch(error){text('jev-retry-note',`检查请求失败：${error.message}`);}
  finally{button.disabled=false;}
});
$('return-live').addEventListener('click',closeDrawer);
$('replay-btn').addEventListener('click',()=>{const rows=asArray(S.live?.signal?.rounds),row=rows.find(r=>r.status==='settled'||r.status==='tie'||r.status==='void')||rows[0];if(row)openRound(roundId(row));});
$('open-latest-round').addEventListener('click',()=>{if(S.latestRound)openRound(roundId(S.latestRound));});
$('drawer-body').addEventListener('click',event=>{if(!event.target.closest('#drawer-show-network'))return;$('audit-overlay').hidden=true;document.body.style.overflow='';BtcNetwork.setStage(true);BtcNetwork.setScene('signal');renderNetwork(S.view||S.live);});
$('drawer-close').addEventListener('click',closeDrawer);$('audit-backdrop').addEventListener('click',closeDrawer);
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!$('audit-overlay').hidden)closeDrawer();});
document.querySelectorAll('[data-price-mode]').forEach(button=>button.addEventListener('click',()=>{S.priceMode=button.dataset.priceMode;document.querySelectorAll('[data-price-mode]').forEach(x=>x.classList.toggle('active',x===button));S.priceSignature=null;if(S.view)renderPrice(S.view,true);}));
$('audit-events').addEventListener('click',event=>{const node=event.target.closest('[data-round]');if(node)openRound(node.dataset.round);});
$('jev-recent').addEventListener('click',event=>{const node=event.target.closest('[data-round]');if(node)openRound(node.dataset.round);});
$('equity-chart').addEventListener('mousemove',event=>{S.chartHover=event.offsetX;if(S.view)drawEquity(S.view);});
$('equity-chart').addEventListener('mouseleave',()=>{S.chartHover=null;$('equity-tooltip').style.display='none';if(S.view)drawEquity(S.view);});
window.addEventListener('resize',()=>{S.priceSignature=null;if(S.view){renderPrice(S.view,true);drawEquity(S.view);}});
const storySteps=[
  {title:'先看：这台机器怎么工作',line:'公开价格先冻结，蓝色直接 Laya、绿色教师框架与紫色 Jev 同题作答；先交答案，再看真实结果。',target:'jev-comparison'},
  {title:'先揭晓：猜得准，也赚得到吗？',line:'蓝色和绿色猜同一批题。先比较猜对率，再看各自从一万美元虚拟资金出发，扣费后还剩多少。',target:'score-board'},
  {title:'它怎么猜：三条并行判断线',line:'同一份冻结行情，蓝色直接 Laya、绿色教师框架、紫色云端 Jev 并行作答；先交答案，随后揭晓。',target:'signal-section'},
  {title:'题目从哪来：真正的交易所价格',line:'这里能看到已发生的成交和当前买卖报价。数据太旧时，就不能继续按正常方式模拟买卖。',target:'market-depth'},
  {title:'从判断到买卖：费用能不能过关',line:'每 30 秒才考虑一次虚拟买卖。新报价、风险和费用都过关，才记入模拟账户；不会真的下单。',target:'portfolio-section'},
  {title:'怎样改进：新方法先参加未来考试',line:'ChatGPT 参与离线设计。新方法先用之后发生的新数据测试，证据不够就不会替换原有账户规则。',target:'research-section'}
];
let storyIndex=0;
function setActiveNav(id){const target=id==='overview'?'start':id;document.querySelectorAll('.section-nav a').forEach(link=>link.classList.toggle('active',link.getAttribute('href')===`#${target}`));}
function showStory(index,jump=false){
  storyIndex=Math.max(0,Math.min(storySteps.length-1,index));const step=storySteps[storyIndex],count=`第 ${storyIndex+1} 步 / 共 ${storySteps.length} 步`;
  for(const id of ['story-step-count','story-dock-count'])text(id,count);
  for(const id of ['story-step-title','story-dock-title'])text(id,step.title);
  for(const id of ['story-step-line','story-dock-line'])text(id,step.line);
  for(const id of ['story-prev','story-dock-prev'])$(id).disabled=storyIndex===0;
  for(const id of ['story-next','story-dock-next'])$(id).disabled=storyIndex===storySteps.length-1;
  document.querySelectorAll('[data-story-step]').forEach(button=>{const active=Number(button.dataset.storyStep)===storyIndex;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
  if(jump){$('story-dock').hidden=false;setActiveNav(step.target);document.getElementById(step.target)?.scrollIntoView({behavior:'smooth',block:'start'});}
}
document.querySelectorAll('.section-nav a').forEach(link=>link.addEventListener('click',()=>setActiveNav(link.hash.slice(1))));
window.addEventListener('hashchange',()=>setActiveNav(location.hash.slice(1)||'overview'));
document.querySelectorAll('[data-story-step]').forEach(button=>button.addEventListener('click',()=>showStory(Number(button.dataset.storyStep),true)));
$('story-prev').addEventListener('click',()=>showStory(storyIndex-1,true));
$('story-next').addEventListener('click',()=>showStory(storyIndex+1,true));
$('story-jump').addEventListener('click',()=>showStory(storyIndex,true));
$('story-dock-prev').addEventListener('click',()=>showStory(storyIndex-1,true));
$('story-dock-next').addEventListener('click',()=>showStory(storyIndex+1,true));
$('story-dock-close').addEventListener('click',()=>{$('story-dock').hidden=true;});
showStory(0);
setActiveNav(location.hash.slice(1)||'start');
BtcNetwork.init();
const updateNote=document.createElement('p');updateNote.id='dashboard-update-note';updateNote.className='muted';updateNote.textContent='等待第一份真实状态；流程结构先显示，数值不补造。';$('jev-comparison').appendChild(updateNote);
refresh();setInterval(refresh,950);setInterval(tick,100);
