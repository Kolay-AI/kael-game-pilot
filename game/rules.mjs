export const RULES=Object.freeze({maxEnergy:100,walk:190,sprint:300,jump:570,gravity:1450,meleeDamage:28,bottles:{frost:{damage:12,duration:3},ember:{damage:38,duration:2},confusion:{damage:6,duration:5}}});
export function damage(hp,amount){return Math.max(0,hp-amount)}
export function collectPage(n){const pages=n+1;return{pages,unlock:pages===3?'FROST-MEISTERSCHAFT':null}}
export function applyPageUnlock(state){if(state.pages<3||state.pageUnlock)return state;const bottles={};for(const [type,count]of Object.entries(state.bottles))bottles[type]=Math.min(5,count+1);return{...state,pageUnlock:true,bottleCapacity:5,bottles}}
export function bottleHit(enemy,type){const r=RULES.bottles[type];if(!r)return enemy;return{...enemy,hp:damage(enemy.hp,r.damage),effect:type,effectTime:r.duration,effectPulse:0,confusionCd:0,confusionDir:enemy.confusionDir||1}}
export function bottleEffectProfile(type){return RULES.bottles[type]||null}
export function respawn(state,checkpoint){return{...state,x:checkpoint.x,y:checkpoint.y,vx:0,vy:0,energy:RULES.maxEnergy}}
export function meleeCanHit(attackId,enemyLastHit){return attackId>0&&attackId!==enemyLastHit}
export function confusionCanStrike(cooldown,hasTarget){return hasTarget&&cooldown<=0}
export function tickCooldown(value,dt){return Math.max(0,value-dt)}
export function setCrouch(body,wantsCrouch,clearAbove=true){const standing=56,crouched=34;if(wantsCrouch&&body.h===standing)return{...body,y:body.y+standing-crouched,h:crouched,duck:true};if(!wantsCrouch&&body.h===crouched&&clearAbove)return{...body,y:body.y-(standing-crouched),h:standing,duck:false};return{...body,duck:body.h===crouched}}
const LIBERATION_NEXT={crack:['cloud',1.1],cloud:['normal',.55],normal:['look',.8],look:['exit',1],exit:['done',0]};
export function advanceLiberation(state,dt){if(state.phase==='alive'||state.phase==='done')return state;const remaining=Math.max(0,state.remaining-dt);if(remaining===0&&LIBERATION_NEXT[state.phase]){const[phase,next]=LIBERATION_NEXT[state.phase];return{phase,remaining:next}}return{...state,remaining}}
export function levelComplete(bossLiberation){return bossLiberation.phase==='done'}
