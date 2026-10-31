## 雪绒的钢铁雄心编辑器 v1.23.11

技术债第 2 项：循环依赖的节点不再叠在一起。

### 问题

国策树/事件树布局时按依赖深度分层：

```js
function dep(id, seen){
  if(seen.has(id)) return 0;      // 循环就在这里断开
  seen.add(id);
  let d = 0;
  for(const p of prereq) d = Math.max(d, dep(p, seen) + 1);
  return d;
}
```

A→B→A 这种循环，两边的深度会算成同一个值：

```
dep(A, {}) → seen={A} → dep(B, {A}) → seen={A,B} → dep(A,{A,B}) 命中 seen → 0
          → B = 0+1 = 1 → A = 1+1 = 2
dep(B, {}) → seen={B} → dep(A, {B}) → seen={B,A} → dep(B,{B,A}) 命中 seen → 0
          → A = 0+1 = 1 → B = 1+1 = 2
```

两个都是 2。同一年、同一深度 → 同一个坐标 → 两个框完全重叠。

### 改法

记录「同一年 + 同一深度」已经占了几个位置，多的横向错开：

```js
const used = {};
arr.forEach(t=>{
  const d = dep(t.id, new Set());
  const slot = used[d] || 0;
  used[d] = slot + 1;
  pos[t.id] = {x: 140 + xi * 340 + slot * 34,
               y: 70 + d * 100 + slot * 8, t};
});
```

第一个占正常位置，后面的往右挪 34px、轻微下移 8px，形成斜排。
不改变深度计算逻辑，只解决视觉重叠。

### 效果

循环里的两个节点变成斜向分开，连线也看得见了。
非循环的正常树位置不变（`slot` 恒为 0）。

### 局限

这只是**视觉修复**，不是把循环改对——循环依赖本身在 HOI4 里也是错的
（国策 A 需要 B，B 又需要 A，游戏里一个都点不了）。

真正的循环检测（在界面上标红提示）没做，留到以后。

### 回归

```
写接口  10/10
```
