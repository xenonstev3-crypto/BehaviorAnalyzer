# `reconstruct_coordinates` 数学说明

对每个 trial 建立右手圆桶坐标系：原点 `O` 是桶底圆心，+Z 从底面圆心指向桶顶中心，+X 为用户在底面中声明的参考方向，+Y 补成右手系。

设原始圆心为 `c`，竖直参考向量为 `v_z`，X 参考向量为 `v_x`：

```text
z_hat       = normalize(v_z)
x_projected = v_x - dot(v_x, z_hat) * z_hat
x_hat       = normalize(x_projected)
y_hat       = normalize(cross(z_hat, x_hat))
p_new       = [dot(p-c,x_hat), dot(p-c,y_hat), dot(p-c,z_hat)]
```

若 `norm(x_projected)` 太小，表示 X 参考近似平行 Z 轴，函数报错“X 参考方向与 Z 轴近似平行，无法建立坐标系”，不会产生伪结果。

程序把 `x_hat`、`y_hat`、`z_hat` 逐行写成 3×3 旋转矩阵 `R`，使用行向量实现：`new = (raw - c) @ R.T`。因此新坐标中底面圆心是 `(0,0,0)`，中心轴沿 `+Z`，底面为 `Z=0`，半径为 `r` 的圆桶壁满足 `sqrt(X²+Y²)=r`。

方向开关不是任意翻转单轴：用户选择翻转 X 或翻转 Y 时，程序同步翻转底面两个轴，使 `X × Y = Z` 仍成立。变换记录会保存开关状态、原点、矩阵、参考来源、时间、版本与质量控制信息。

本阶段实现的是默认的 session-level 变换。固定环境标记若有明显帧间漂移，程序拒绝 session-level 结果并提示检查标记或将来使用 frame-level；它不会偷偷把漂移平均掉。
