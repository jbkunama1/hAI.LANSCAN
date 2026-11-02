'use strict';
(()=>{
  const palette=document.getElementById('themePalette');
  const toggle=document.getElementById('themeToggle');
  if(!palette||!toggle)return;
  const root=document.documentElement;
  const palettes=['ocean','forest','sunset','violet'];
  let pref=null;
  try{
    pref=JSON.parse(localStorage.getItem('lanscan-appearance'));
    if(!pref){const old=localStorage.getItem('lanscan-theme');if(old)pref={palette:'ocean',mode:old==='light'?'light':'dark'};}
  }catch(e){}
  function sync(){
    const dark=root.dataset.theme!=='light';
    toggle.setAttribute('aria-checked',String(dark));
    toggle.title=dark?'Zu Hell wechseln':'Zu Dunkel wechseln';
    document.getElementById('themeIcon').textContent=dark?'🌙':'☀️';
    palette.value=palettes.includes(root.dataset.palette)?root.dataset.palette:'ocean';
  }
  function apply(color,mode,persist){
    root.dataset.palette=palettes.includes(color)?color:'ocean';
    root.dataset.theme=mode==='light'?'light':'dark';
    sync();
    if(persist)try{localStorage.setItem('lanscan-appearance',JSON.stringify({palette:root.dataset.palette,mode:root.dataset.theme}));}catch(e){}
  }
  apply(pref&&pref.palette,pref&&pref.mode?pref.mode:root.dataset.theme==='light'?'light':'dark',false);
  palette.onchange=()=>apply(palette.value,root.dataset.theme,true);
  toggle.onclick=()=>apply(palette.value,root.dataset.theme==='light'?'dark':'light',true);
  new MutationObserver(sync).observe(root,{attributes:true,attributeFilter:['data-theme','data-palette']});
  const field=document.getElementById('targets');
  const chosen=new URLSearchParams(location.search).get('scanHost');
  if(field&&chosen&&/^\d{1,3}(\.\d{1,3}){3}$/.test(chosen)){
    field.value=chosen;
    const button=document.querySelector('[data-view="scan"]');if(button)button.click();
  }
})();
