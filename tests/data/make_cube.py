"""Génère cube.med : cube de 10 mm, groupes VOL (volume) et X0, X1, Y0, Y1, Z0, Z1 (faces).

Usage : python tests/data/make_cube.py [sortie.med] [taille_maille] [--hexa] [--order2]
"""

import sys
from pathlib import Path

import gmsh

L = 10.0
EPS = 1e-6


def make_cube(path: Path, size: float = 2.5, hexa: bool = False, order: int = 1) -> Path:
    gmsh.initialize()
    gmsh.option.setNumber("General.Terminal", 0)
    try:
        gmsh.model.add("cube")
        gmsh.model.occ.addBox(0, 0, 0, L, L, L)
        gmsh.model.occ.synchronize()
        gmsh.model.addPhysicalGroup(3, [1], name="VOL")
        for axis, name in enumerate("XYZ"):
            for value, suffix in ((0.0, "0"), (L, "1")):
                lo = [-EPS] * 3
                hi = [L + EPS] * 3
                lo[axis], hi[axis] = value - EPS, value + EPS
                faces = gmsh.model.getEntitiesInBoundingBox(*lo, *hi, dim=2)
                gmsh.model.addPhysicalGroup(2, [tag for _, tag in faces], name=name + suffix)
        gmsh.option.setNumber("Mesh.MeshSizeMax", size)
        if hexa:
            n = round(L / size) + 1
            for dim, tag in gmsh.model.getEntities(1):
                gmsh.model.mesh.setTransfiniteCurve(tag, n)
            for dim, tag in gmsh.model.getEntities(2):
                gmsh.model.mesh.setTransfiniteSurface(tag)
                gmsh.model.mesh.setRecombine(2, tag)
            gmsh.model.mesh.setTransfiniteVolume(1)
            gmsh.model.mesh.setRecombine(3, 1)
        gmsh.model.mesh.generate(3)
        if order > 1:
            gmsh.option.setNumber("Mesh.SecondOrderIncomplete", 1)
            gmsh.model.mesh.setOrder(order)
        path.parent.mkdir(parents=True, exist_ok=True)
        gmsh.write(str(path))
    finally:
        gmsh.finalize()
    return path


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else Path(__file__).with_name("cube.med")
    size = float(args[1]) if len(args) > 1 else 2.5
    print(make_cube(out, size, hexa="--hexa" in sys.argv, order=2 if "--order2" in sys.argv else 1))
