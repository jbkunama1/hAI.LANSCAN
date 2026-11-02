'use strict';
(()=>{
  const select=document.getElementById('quickTheme');
  if(!select)return;
  const themes=['light','dark','ocean'];
  let saved=null;try{saved=localStorage.getItem('lanscan-theme');}catch(e){}
  const theme=themes.includes(saved)?saved:document.documentElement.dataset.theme;
  select.value=themes.includes(theme)?theme:'ocean';
  document.documentElement.dataset.theme=select.value;
  select.onchange=()=>{document.documentElement.dataset.theme=select.value;try{localStorage.setItem('lanscan-theme',select.value);}catch(e){}};
  const field=document.getElementById('targets');
  const chosen=new URLSearchParams(location.search).get('scanHost');
  if(field&&chosen&&/^\d{1,3}(\.\d{1,3}){3}$/.test(chosen)){
    field.value=chosen;
    const button=document.querySelector('[data-view="scan"]');if(button)button.click();
  }
})();
