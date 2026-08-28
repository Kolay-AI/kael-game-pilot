export const LEVEL_WIDTH=5400;
export const ENEMY_DESCRIPTORS=Object.freeze([
 {id:'farmer-1',type:'farmer',x:900,y:415,hp:70,damage:12,activation:120,tether:260,terrainY:470,minPlayerX:821},
 {id:'animal-1',type:'animal',x:1840,y:432,hp:60,damage:10,activation:520,tether:250,terrainY:470},
 {id:'brute-1',type:'brute',x:2480,y:410,hp:115,damage:20,activation:200,tether:270,terrainY:470,minPlayerX:2200},
 {id:'farmer-2',type:'farmer',x:2760,y:415,hp:70,damage:12,activation:180,tether:230,terrainY:470,minPlayerX:2600},
 {id:'animal-2',type:'animal',x:3000,y:432,hp:60,damage:10,activation:180,tether:230,terrainY:470,minPlayerX:2840},
 {id:'boss-1',type:'boss',x:4740,y:394,hp:260,damage:26,activation:700,tether:420,arenaGate:4300,terrainY:470}
]);

export function createEnemy(d){return{id:d.id,type:d.type,x:d.x,y:d.y,spawnX:d.x,spawnY:d.y,terrainY:d.terrainY,w:d.type==='boss'?70:d.type==='brute'?52:d.type==='animal'?44:46,h:d.type==='boss'?76:d.type==='brute'?60:d.type==='animal'?38:55,vx:0,vy:0,hp:d.hp,max:d.hp,dmg:d.damage,activation:d.activation,tether:d.tether,arenaGate:d.arenaGate??null,minPlayerX:d.minPlayerX??null,active:false,visible:false,alive:true,freed:false,state:'hostile',hostile:true,hitbox:true,evacDir:1,effect:'',effectTime:0,hit:0,lastMelee:0,confusionCd:0,liberation:{phase:'alive',remaining:0},exit:0}}
export function createEnemies(){return ENEMY_DESCRIPTORS.map(createEnemy)}
export function updateEnemyActivation(e,playerX,viewLeft,viewWidth){
 const gate=e.arenaGate==null||playerX>=e.arenaGate;
 const unlocked=e.minPlayerX==null||playerX>e.minPlayerX;
 const near=Math.abs(playerX-e.spawnX)<=e.activation;
 const visible=e.x+e.w>=viewLeft-80&&e.x<=viewLeft+viewWidth+80;
 if(e.freed)return e;
 return{...e,active:e.alive&&gate&&unlocked&&(e.active||near||visible),visible:visible&&gate&&unlocked};
}
export function enforceEnemyBounds(e){
 if(!e.alive)return e;
 if(e.y>610||Math.abs(e.x-e.spawnX)>e.tether+80)return{...e,x:e.spawnX,y:e.spawnY,vx:0,vy:0};
 return{...e,x:Math.max(e.spawnX-e.tether,Math.min(e.spawnX+e.tether,e.x))};
}