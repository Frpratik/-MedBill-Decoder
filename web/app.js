'use strict';
const $ = id => document.getElementById(id);
let busy = false;
const money = value => value === null || value === undefined ? '—' : new Intl.NumberFormat('en-US', {style:'currency',currency:'USD'}).format(Number(value));
function node(tag, text, className) { const el=document.createElement(tag); if(text!==undefined) el.textContent=text; if(className)el.className=className; return el; }
function clearReport(){ $('report').hidden=true; $('clear').hidden=true; $('empty').hidden=false; $('rows').replaceChildren(); $('questions').replaceChildren(); for(const id of ['report-context','guidance','difference','compared','excluded','error','status'])$(id).textContent=''; $('error').hidden=true; }
function state(on){busy=on; document.querySelectorAll('button,input,select').forEach(el=>el.disabled=on); $('status').textContent=on?'Reading the sample and comparing its charges. This can take a minute…':''; $('results' )?.setAttribute('aria-busy',String(on));}
function showError(text){$('error').textContent=text;$('error').hidden=false;}
async function init(){try{const response=await fetch('/api/localities');if(!response.ok)throw new Error();const list=await response.json();$('locality').replaceChildren();for(const entry of list){const value=`${entry.carrier}/${entry.locality}`;const label=value==='01112/05'?'San Francisco · 01112 / 05':`CMS ${entry.carrier} / ${entry.locality}`;const option=new Option(label,value);option.selected=value==='01112/05';$('locality').add(option);}}catch{showError('Reference areas could not load. Check the local reference database and reload the page.');}}
function render(report){
  $('empty').hidden=true;$('report').hidden=false;$('clear').hidden=false;
  const s=report.summary,c=report.context;
  $('report-context').textContent=`${report.ocr.page_count} page(s) · ${s.candidate_rows} line items · CMS ${c.carrier} / ${c.locality} · ${c.setting} · ${c.category}`;
  $('guidance').textContent=report.guidance;
  $('difference').textContent=s.amount_above_medicare_benchmark_usd===null?'Not calculated':money(s.amount_above_medicare_benchmark_usd);
  $('compared').textContent=`${s.compared_rows} / ${s.candidate_rows}`;$('excluded').textContent=String(s.excluded_rows);
  $('rows').replaceChildren();$('questions').replaceChildren();
  if(!report.items.length){$('rows').append(node('tr'));const td=node('td','No service rows could be read. Try a clearer itemized bill.');td.colSpan=5;$('rows').lastChild.append(td);$('questions').append(node('li','Can you provide a clear itemized bill showing service dates, codes, units and charges?'));}
  for(const item of report.items){
    const tr=node('tr'),service=node('td'),ex=item.explanation_result;
    service.append(node('span',`${item.code||'Code needs review'}${item.modifier?' · '+item.modifier:''}`,'service-code'),node('div',ex.explanation,'service-text'));
    const detail=node('details',undefined,'row-detail');detail.append(node('summary','View reference & details'));
    if(ex.official_description)detail.append(node('p',`CMS: ${ex.official_description} · Source: ${ex.description_source_id}`));
    if(item.service_date)detail.append(node('p',`Service date: ${item.service_date}`));
    if(ex.benchmark_explanation)detail.append(node('p',ex.benchmark_explanation));
    if(item.statistics)detail.append(node('p',`Geographic 95th percentile: ${money(item.statistics.p95_usd)} · ${item.statistics.n} matching Medicare localities.`));
    for(const warning of item.warnings||[])detail.append(node('p',warning));
    if(item.issues?.length)detail.append(node('p',`Reading issues: ${item.issues.join(', ')}`));
    service.append(detail);tr.append(service,node('td',item.quantity??'—'),node('td',money(item.charged_cents===null?null:item.charged_cents/100),'amount'),node('td',money(item.unit_benchmark_usd),'amount'));
    const status=node('td');const label=item.flag===true?'Above benchmark':item.availability==='compared'?(item.flag===false?'Not flagged':'Limited comparison'):item.availability==='ocr_review_required'?'Check reading':item.availability==='unknown_code'?'Code not in reference':item.availability==='unsupported_date'?'Date not supported':'No comparison';
    status.append(node('span',label,`badge ${item.flag===true?'flag':item.availability==='compared'?'ok':''}`));tr.append(status);$('rows').append(tr);
    $('questions').append(node('li',`${item.code||'Unreadable line'}: ${ex.question}`));
  }
}
async function submit(file){
  if(busy)return;
  clearReport();if(!file){showError('Choose a synthetic sample file first.');return;}
  if(!file.size||file.size>20*1024*1024){showError('Choose a nonempty file no larger than 20 MiB.');return;}
  if(!$('locality').value){showError('Select a reference area first.');return;}
  state(true);
  try{const [carrier,locality]=$('locality').value.split('/');const query=new URLSearchParams({synthetic:'true',carrier,locality,setting:$('setting').value,category:$('category').value});
    const response=await fetch(`/api/decode?${query}`,{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:file});
    const result=await response.json();if(!response.ok)throw new Error(typeof result.detail==='string'?result.detail:'Check the comparison settings and try again.');render(result);
  }catch(error){showError(error.message||'Could not reach the local server. Please try again.');}finally{state(false);}
}
$('upload-form').addEventListener('submit',event=>{event.preventDefault();if($('synthetic').checked)submit($('bill').files[0]);});
$('bill').addEventListener('change',()=>{$('file-label').textContent=$('bill').files[0]?.name||'No file selected';clearReport();});
for(const id of ['locality','setting','category'])$(id).addEventListener('change',clearReport);
$('clear').addEventListener('click',()=>{clearReport();$('bill').value='';$('file-label').textContent='No file selected';$('synthetic').checked=false;});
document.querySelectorAll('[data-sample]').forEach(button=>button.addEventListener('click',async()=>{if(busy)return;clearReport();state(true);try{const response=await fetch(`/api/samples/${button.dataset.sample}`);if(!response.ok)throw new Error('Sample file could not be loaded.');const file=await response.blob();$('bill').value='';$('file-label').textContent=`Synthetic sample: ${button.textContent}`;state(false);await submit(file);}catch(error){showError(error.message);state(false);}}));
init();
