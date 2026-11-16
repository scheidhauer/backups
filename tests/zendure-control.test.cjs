// Ausführen ab Node.js 22.13: node tests/zendure-control.test.cjs
const { stripTypeScriptTypes } = require('node:module');
const fs = require('fs'); const vm = require('vm'); const assert = require('node:assert/strict');
const source = fs.readFileSync(require('node:path').join(__dirname, '../PV-Werte-berechnen.ts'),'utf8');
const section=source.slice(source.indexOf('const MAX_POWER'),source.indexOf('function getCurrentZendurePower'));
const compiled = stripTypeScriptTypes(section+'\nglobalThis.Hyper = Hyper;');
let now=1000000, states, writes, ctx;
const base='zendure-solarflow.0.test.device';
function reset(actual=0){
 now=1000000;states=new Map();writes=[];
 const values={lastUpdate:now, outputHomePower:Math.max(0,actual),gridInputPower:Math.max(0,-actual),electricLevel:50,minSoc:10,socSet:90,packNum:2,socStatus:0,inverseMaxPower:1200};
 for(const [k,v] of Object.entries(values)) states.set(base+'.'+k,v);
 class Clock extends Date {constructor(...a){super(...(a.length?a:[now]))} static now(){return now}}
 ctx={Date:Clock,console:{warn(){},info(){},debug(){}},getStateIOB:id=>({val:states.get(id)}),existsStateIOB:id=>states.has(id),getValue:id=>states.get(id),getObjectIOB:()=>({common:{name:{de:'Test'}}}),setStateIOB:(id,val,ack)=>writes.push({id,val,ack})};
 vm.createContext(ctx);vm.runInContext(compiled,ctx);return new ctx.Hyper(base);
}
function advance(ms){now+=ms;states.set(base+'.lastUpdate',now)}
function send(h,n){h.setAcValue(n)}
let h=reset(400);send(h,0);assert.equal(writes.at(-1).val,0); // first stop despite ongoing output
h=reset();send(h,200);advance(1000);send(h,0);assert.deepEqual(writes.map(w=>w.val),[200,0]);
h=reset();send(h,200);advance(181000);send(h,250);advance(1000);send(h,-200);assert.equal(writes.at(-1).val,250);assert.equal(h.lastDirection,1);advance(30000);send(h,-200);assert.equal(writes.at(-1).val,-200); // throttled request must not set direction
advance(1000);send(h,200);assert.equal(writes.at(-1).val,0);advance(180000);send(h,200);assert.equal(writes.at(-1).val,200);
h=reset(-400);send(h,400);assert.equal(writes.at(-1).val,0);advance(181000);send(h,400);assert.equal(writes.at(-1).val,400); // restart conservatively remembers measured direction
h=reset();send(h,200);advance(1000);send(h,300);assert.equal(writes.length,1);advance(30000);send(h,300);assert.equal(writes.at(-1).val,300);
h=reset();send(h,500);advance(61000);send(h,500);advance(61000);send(h,500);advance(61000);send(h,500);advance(61000);send(h,500);advance(61000);send(h,500);assert.equal(writes.length,3); // two retries only
h=reset();send(h,-500);for(let i=0;i<8;i++){advance(61000);send(h,-500)}assert.equal(writes.length,1);
h=reset();states.delete(base+'.socStatus');send(h,500);for(let i=0;i<8;i++){advance(61000);send(h,500)}assert.equal(writes.length,1);
h=reset();states.set(base+'.socStatus',1);send(h,0);send(h,500);assert.equal(writes.length,0); // no intervention during calibration
h=reset();send(h,500);now+=601000;send(h,700);send(h,700);assert.deepEqual(writes.map(w=>w.val),[500,0]);advance(1000);h.resume();send(h,700);assert.equal(writes.at(-1).val,700);
h=reset();send(h,NaN);assert.equal(writes.length,0);
assert(!source.includes('this.setValue(AC_MODE_ID'));
assert(source.includes('availableHypers.includes(lastChoosenHyper)'));
assert(source.includes('this.isControlled() && desiredPower > 0'));
assert(writes.every(w=>w.ack===false));
stripTypeScriptTypes(source);
console.log('PASS: syntax; first/urgent stop; rate limiting; deferred direction; direction lock; restart; bounded retries; no charging retries; missing status; calibration; stale telemetry/recovery; invalid target; selection guards.');

// Gesamte Verteilung mit zwei Geräten und regelmäßigem Regelzyklus.
h=reset();
const fleetIds=['zendure-solarflow.0.gDa3tb.dT4s7652','zendure-solarflow.0.gDa3tb.0261mkBX'];
for(const id of fleetIds){
 for(const [key,val] of [...states]) if(key.startsWith(base+'.')) states.set(id+key.slice(base.length),val);
 states.set('0_userdata.0.PV.AkkuSteuerung-'+id.split('.').at(-1),true);
}
states.set('alias.0.PV.Einspeisung/Verbrauch',1500);
ctx.getStateIOB=id=>({val:states.get(id),ts:now});
ctx.onIOB=()=>{};ctx.scheduleIOB=()=>{};
ctx.pvErzeugung='pv';ctx.currentPower='alias.0.PV.Einspeisung/Verbrauch';ctx.eigenverbrauch='eigenverbrauch';
ctx.setStateClever=(id,value,ack)=>ctx.setStateIOB(id,value,ack);
const rest=source.slice(source.indexOf('function getCurrentZendurePower'),source.indexOf('function setChargeLimitAllHypers'));
vm.runInContext(stripTypeScriptTypes(rest+'\nglobalThis.adaptZendure = adaptZendure; globalThis.chooseHyper = getHyperWithHighestOrLowestCapacity;'),ctx);
const commands=()=>writes.filter(w=>w.id.endsWith('.control.setDeviceAutomationInOutLimit'));
ctx.adaptZendure();assert.equal(commands().length,2);assert(commands().every(w=>w.val===753));
// Kalibriert ein Hyper, wird nur der andere einmal gestoppt.
states.set(fleetIds[0]+'.socStatus',1);ctx.adaptZendure();ctx.adaptZendure();assert.equal(commands().length,3);assert.equal(commands().at(-1).id,fleetIds[1]+'.control.setDeviceAutomationInOutLimit');assert.equal(commands().at(-1).val,0);
states.set(fleetIds[0]+'.socStatus',0);ctx.adaptZendure();assert.equal(commands().length,5);
// Ein veralteter Zähler führt einmalig zu Stopp, danach keine weiteren Aufträge.
ctx.getStateIOB=id=>({val:states.get(id),ts:now-121000});ctx.adaptZendure();ctx.adaptZendure();assert.equal(commands().length,7);assert(commands().slice(-2).every(w=>w.val===0));
// Ein nicht verfügbarer früherer Favorit darf nicht zurück in die Auswahl kommen.
const fleet=ctx.Hyper.getAllHypers();vm.runInContext('lastChoosenHyper = Hyper.getAllHypers()[0];',ctx);
assert.equal(ctx.chooseHyper([fleet[1]],500),fleet[1]);
// Ein manuell geführtes Gerät wird nicht durch die Mindest-SOC-Nachladung überschrieben.
states.set('0_userdata.0.PV.AkkuSteuerung-dT4s7652',false);states.set(fleetIds[0]+'.electricLevel',5);
const count=commands().length;assert.equal(fleet[0].checkBelowDischargeLimit(500),true);assert.equal(commands().length,count);
console.log('PASS: two-device distribution; fleet calibration pause/recovery; stale meter; unavailable favourite; manual override preserved.');
