export const KAEL_POSES=Object.freeze(['idle','walk','sprint','turn','takeoff','jumpUp','doubleJump','flip','fall','land','crouch','melee','throw','hit']);
export const ANIMATIONS=Object.freeze({
 idle:{fps:4,frames:8,loop:true},walk:{fps:12,frames:12,loop:true},sprint:{fps:16,frames:12,loop:true},turn:{fps:18,frames:4,loop:false},
 takeoff:{fps:18,frames:4,loop:false},jumpUp:{fps:8,frames:3,loop:false},doubleJump:{fps:12,frames:10,loop:false,phases:['boostStart','armsBack','armsForward','kneesUp','fastLegs','fastLegs','airPeak','balance','fallTransition','fallTransition']},flip:{fps:20,frames:16,loop:false,phases:['trigger','trigger','tuck','tuck','entry','entry','mid','mid','mid','late','late','late','open','open','fallTransition','fallTransition']},fall:{fps:8,frames:3,loop:false},land:{fps:18,frames:6,loop:false},
 crouch:{fps:1,frames:1,loop:false},melee:{fps:15,frames:8,loop:false,phases:['windup','windup','active','active','active','recover','recover','recover']},
 throw:{fps:14,frames:8,loop:false,phases:['windup','windup','release','release','recover','recover','recover','recover']},hit:{fps:18,frames:5,loop:false}
});
export function approach(value,target,amount){return value<target?Math.min(target,value+amount):Math.max(target,value-amount)}
export function horizontalMotion(body,{axis=0,sprint=false,onGround=true,knockback=0},dt){
 if(knockback>0)return{vx:body.vx,face:body.face};
 const target=axis*(sprint?300:190),turning=axis&&Math.sign(body.vx)&&Math.sign(body.vx)!==axis;
 const accel=onGround?(turning?2500:axis?1750:2100):(axis?720:180);
 return{vx:approach(body.vx,target,accel*dt),face:axis?axis:body.face,turnTime:turning&&onGround?.12:0};
}
export function animationFrame(pose,elapsed){const a=ANIMATIONS[pose]||ANIMATIONS.idle;const raw=Math.floor(Math.max(0,elapsed)*a.fps);return a.loop?raw%a.frames:Math.min(a.frames-1,raw)}
export function animationPhase(pose,frame){return ANIMATIONS[pose]?.phases?.[frame]??pose}
export function kaelEyeState(blink=false){return blink?'EYES_BLINK':'EYES_OPEN'}
// Eyes stay open for most of the cycle; the short closed interval is a blink.
export function kaelBlinkState(time=0){const cycle=((Math.max(0,time)%4.6));return kaelEyeState(cycle>=4.38&&cycle<4.50)}
export function canDoubleJump(p){return !!p&&!p.on&&!p.doubleJumpUsed&&p.hitTime<=0&&!p.duck}
export function canMeleeDamage(player,enemyLastHit){return player.pose==='melee'&&player.attack>0&&animationPhase('melee',animationFrame('melee',player.animTime))==='active'&&player.attackId>0&&player.attackId!==enemyLastHit}
export function kaelPose(p,axis,sprint){if(p.hitTime>0)return'hit';if(p.attack>0)return'melee';if(p.throwTime>0)return'throw';if(p.duck)return'crouch';if(p.doubleJumpTime>0)return'doubleJump';if(p.takeoffTime>0)return'takeoff';if(!p.on)return p.vy<0?'jumpUp':'fall';if(p.landTime>0)return'land';if(p.turnActive||p.turnTime>0)return'turn';if(axis||Math.abs(p.vx)>18)return sprint?'sprint':'walk';return'idle'}
// Eight distinct contact/passing/push-off poses. Values are [leftX,leftY,rightX,rightY]
// and deliberately move the boots through a full stride, rather than merely bobbing.
const WALK_LEGS=[[-12,0,12,-4],[-9,-2,10,0],[-5,-4,7,0],[0,-5,3,0],[5,-3,-1,0],[9,-1,-6,0],[12,0,-10,-4],[10,0,-8,-2],[7,0,-5,-4],[3,0,0,-2],[-1,0,5,-1],[-7,0,10,-3]];
const SPRINT_LEGS=[[-18,0,17,-8],[-14,-4,14,0],[-9,-8,10,0],[-3,-12,5,0],[4,-9,-1,0],[11,-3,-8,0],[17,0,-15,-8],[13,0,-12,-5],[8,0,-9,-9],[2,0,-3,-6],[-5,0,5,-3],[-12,0,13,-5]];
const FLIP_META=[[-2,0,2,-3],[-3,-1,3,-3],[-4,-2,4,-2],[-4,-3,5,-1],[-3,-4,6,-2],[-2,-4,6,-3],[-1,-3,5,-4],[0,-2,4,-4],[1,-1,3,-3],[2,0,2,-2],[3,0,1,-1],[4,0,0,0],[5,0,-1,0],[5,0,-1,1],[4,0,0,1],[3,0,1,0]];
export function kaelRenderFrame(pose,frame){let raw=[0,0,0,0],upperY=0,lean=0,bodyTilt=0,rotation=0;if(pose==='walk')raw=WALK_LEGS[frame%12];if(pose==='sprint'){raw=SPRINT_LEGS[frame%12];lean=5;bodyTilt=-2}if(pose==='jumpUp')raw=[[-3,1,5,-3],[-2,0,4,-5],[1,-2,5,-6]][frame%3];if(pose==='flip'){raw=FLIP_META[Math.min(15,Math.max(0,frame))];rotation=(Math.min(15,Math.max(0,frame))/15)*Math.PI*2;upperY=-3}if(pose==='fall')raw=[[4,-3,-4,0],[6,-1,-6,2],[3,1,-2,4]][frame%3];if(pose==='melee'){const phase=frame<2?'windup':frame<5?'active':'recover',step=frame%5+1;raw=step===2?(phase==='active'?[-5,0,9,-5]:[-2,1,4,-1]):step===3?(phase==='active'?[5,-3,-4,1]:[2,0,-2,1]):step===5?(phase==='active'?[-2,2,3,2]:[0,1,1,1]):(phase==='active'?[3,-1,-2,1]:[0,0,0,0]);lean=phase==='active'?2:phase==='windup'?-1:0}if(pose==='idle'||pose==='walk'||pose==='sprint')upperY=pose==='idle'?[0,-1,0,1,0,-1,0,1][frame%8]:[1,0,-1,0,0,-1,0,1,0,-1,0,1][frame%12];if(pose==='crouch')upperY=17;if(pose==='takeoff')raw=frame<2?[-2,3,3,2]:[-3,0,4,-4];if(pose==='land')raw=frame<2?[2,-1,-2,0]:frame<4?[0,2,2,1]:[0,0,0,0];if(pose==='takeoff'||pose==='land')upperY=frame<2?5:2;if(pose==='hit')lean=-4;const floor=Math.max(raw[1],raw[3],0),legs=[raw[0],raw[1]-floor,raw[2],raw[3]-floor];
 // Arms counter-swing against the left leg. The sign is intentionally not
 // derived from facing: mirroring the drawing mirrors the pose, never time.
 const armSwing=pose==='sprint'?legs[0]*1.15:pose==='walk'?legs[0]*.95:0;return{legs,upperY,lean,bodyTilt,armSwing,rotation,blink:pose==='idle'&&(frame===2||frame===6),bootBottoms:[legs[1],legs[3]]}}
export function doubleJumpRenderFrame(frame){const f=Math.max(0,Math.min(9,frame)),legs=[[-4,1,6,-2],[-8,0,9,-5],[-11,-3,12,-8],[-6,-7,8,-12],[2,-10,-4,-5],[10,-6,-11,-2],[7,-2,-8,2],[3,0,-4,-1],[-1,0,3,-1],[-3,1,4,-2]][f];const upper=[1,0,-1,-2,-2,-1,0,1,1,0][f],arms=[-5,-10,12,10,4,-2,-6,-3,2,4][f];return{legs,upperY:upper,lean:f<4?-1:f>7?1:0,bodyTilt:0,armSwing:arms,rotation:0,blink:false,bootBottoms:[legs[1],legs[3]]}}

export const KAEL_POSE_INVARIANTS=Object.freeze({head:1,torso:1,arms:2,hands:2,legs:2,feet:2});
export function validateKaelPoseDefinition(pose){return KAEL_POSES.includes(pose)&&KAEL_POSE_INVARIANTS.head===1&&KAEL_POSE_INVARIANTS.torso===1&&KAEL_POSE_INVARIANTS.arms===2&&KAEL_POSE_INVARIANTS.hands===2&&KAEL_POSE_INVARIANTS.legs===2&&KAEL_POSE_INVARIANTS.feet===2}
export function facingTransform(face,pivotX){return{scaleX:face<0?-1:1,translateX:pivotX}}
export function actionAnchors(pose,face){const reach=pose==='melee'?34:pose==='throw'?25:18;return{hand:{x:face*reach,y:pose==='crouch'?13:2},projectile:{x:face*28,y:pose==='crouch'?-1:-12}}}
export function renderMetrics(player){return{pivotX:player.x+player.w/2,footY:player.y+player.h}}
export function projectileSpawn(player,size=12){const m=renderMetrics(player),a=actionAnchors('throw',player.face).projectile;return{x:m.pivotX+a.x-size/2,y:player.y+player.h/2+a.y-size/2,w:size,h:size,vx:player.face*430,centerX:m.pivotX+a.x}}
export function meleeHitbox(player){const m=renderMetrics(player),a=actionAnchors('melee',player.face).hand,w=50;const centerX=m.pivotX+a.x+player.face*w/2;return{x:centerX-w/2,y:player.y+8,w,h:42,centerX}}

export function beginLiberation(enemy){return{...enemy,alive:false,freed:true,state:'liberating',active:false,hostile:false,hitbox:false,hp:0,vx:0,liberation:{phase:'crack',remaining:.7}}}
export function liberationMode(enemy){return enemy.freed?(enemy.state==='despawned'?'hidden':'normal'):(enemy.alive&&enemy.hostile!==false?'cursed':'hidden')}
export function enemyRenderClass(enemy){const base=liberationMode(enemy),phase=enemy.liberation?.phase;if(base==='hidden')return{mode:'hidden',drawCursed:false,drawNormal:false,drawShell:false,drawCloud:false,hidden:true};if(base==='cursed')return{mode:'cursed',drawCursed:true,drawNormal:false,drawShell:false,drawCloud:false,hidden:false};if(phase==='crack')return{mode:'shell',drawCursed:false,drawNormal:false,drawShell:true,drawCloud:false,hidden:false};if(phase==='cloud')return{mode:'cloud',drawCursed:false,drawNormal:false,drawShell:false,drawCloud:true,hidden:false};return{mode:'normal',drawCursed:false,drawNormal:true,drawShell:false,drawCloud:false,hidden:false}}
export function groundAt(platforms,x,y,tolerance=16){return platforms.some(q=>x>=q[0]&&x<=q[0]+q[2]&&q[1]>=y-tolerance&&q[1]<=y+tolerance)}
export function scanGap(platforms,x,footY,dir,maxJump=80,step=8){for(let d=step;d<=maxJump;d+=step)if(groundAt(platforms,x+dir*d,footY))return d;return Infinity}
export function evacuationStep(entity,platforms,dt,levelWidth,viewLeft=0,viewWidth=960){
 if(!entity.freed||entity.state!=='evacuating')return entity;
 let e={...entity,hostile:false,active:false,hitbox:false};const speed=e.type==='animal'?185:120,dir=e.evacDir||1,foot=e.y+e.h;
 const ahead=e.x+(dir>0?e.w+12:-12),supported=groundAt(platforms,ahead,foot),gap=supported?0:scanGap(platforms,ahead,foot,dir);
 if(!supported&&gap<=80&&e.on){e.vy=-360;e.on=false}else if(!supported&&gap===Infinity){e.evacDir=-dir;e.vx=0;return e}
 e.vx=(e.evacDir||dir)*speed;
 const margin=80,offscreen=e.x+e.w<Math.max(-margin,viewLeft-margin)||e.x>Math.min(levelWidth+margin,viewLeft+viewWidth+margin);if(offscreen&&e.liberation?.phase==='done')return{...e,state:'despawned',visible:false,vx:0};
 return e;
}

export function createArko(x,y){return{x,y,face:1,state:'ready',target:null,stateTime:0,cooldown:0,visible:true,uses:0}}
export function arkoHitProfile(enemyType){return enemyType==='boss'?{damage:8,stun:.35,reaction:'flinch'}:{damage:15,stun:1.1,reaction:'stun'}}
export function resolveArkoImpact(enemy){if(!enemy?.alive||enemy.freed||enemy.hitbox===false)return null;return arkoHitProfile(enemy.type)}
export function applyArkoReaction(enemy,profile){return{...enemy,effect:profile.reaction,effectTime:profile.stun}}
export function enemyReactionMotion(enemyType,effect,effectTime,chaseDir,currentVx=0){const chase=chaseDir*(enemyType==='animal'?90:enemyType==='boss'?65:enemyType==='brute'?48:55);if(effectTime>0&&effect==='stun')return{vx:0,reacting:true,mode:'stun'};if(effectTime>0&&effect==='flinch'){const away=Math.sign(currentVx)||-chaseDir||-1;return{vx:away*Math.max(70,Math.min(180,Math.abs(currentVx)*.88)),reacting:true,mode:'flinch'}}return{vx:chase,reacting:false,mode:'chase'}}
export function startArkoDive(a,target,player,maxRange=620){if(a.state!=='ready'||!target||!target.alive||Math.abs(target.x-player.x)>maxRange)return a;return{...a,face:Math.sign(target.x-a.x)||player.face||1,state:'dive',target,stateTime:1.25,uses:a.uses+1}}
export function tickArko(a,dt,player,onHit){let n={...a,cooldown:Math.max(0,a.cooldown-dt),stateTime:Math.max(0,a.stateTime-dt),visible:true};const home={x:player.x-50*player.face,y:player.y-64+Math.sin((n.cooldown+n.stateTime)*7)*4};
 if(n.state==='dive'){if(!n.target?.alive||n.stateTime<=0)n={...n,state:'return',target:null,stateTime:1.4};else{const arc=-Math.sin(Math.max(0,1.25-n.stateTime)*Math.PI/1.25)*34;n.x+=(n.target.x-n.x)*Math.min(1,dt*10);n.y+=(n.target.y+arc-n.y)*Math.min(1,dt*10);if(Math.hypot(n.x-n.target.x,n.y-n.target.y)<32){onHit?.(n.target);n={...n,state:'return',target:null,stateTime:1.4}}}}
 else if(n.state==='return'){n.x+=(home.x-n.x)*Math.min(1,dt*9);n.y+=(home.y-n.y)*Math.min(1,dt*9);if(Math.hypot(n.x-home.x,n.y-home.y)<12||n.stateTime<=0)n={...n,state:'cooldown',cooldown:3,stateTime:0}}
 else{n.x+=(home.x-n.x)*Math.min(1,dt*5);n.y+=(home.y-n.y)*Math.min(1,dt*5);n.face=player.face||1;if(n.state==='cooldown'&&n.cooldown<=0)n={...n,state:'ready'}}return n}

export function liberationVisual(phase){return{shell:['crack','cloud'].includes(phase),cloud:phase==='cloud',normal:['normal','look','exit','done'].includes(phase),look:phase==='look',leaving:['exit','done'].includes(phase)}}
