"""Research implementations used by the algorithm-comparison feature.

* dtdp_probvns.py - Prob-VNS for the Delivery Territory Design Problem, Aly, Gabor, Mladenovic,
  Sleptchenko (2024), C&OR 170, 106756. Copied from
  D:\\territory problem\\TerritoryDesign_PaperFaithful\\DTDPAlgorithms_paper.py (paper-faithful version).
* paper_milp.py - MTDP / CTDP MILP of Salazar-Aguilar, Rios-Mercado, Cabrera-Rios (2011) as written in
  the paper (ICGP-TDP with connectivity cuts), solved with CPLEX through GAMSPy (needs a GAMSPy license).
  Copied from D:\\territory problem\\Code\\NASE-Code. The former OR-Tools exact_milp.py was removed.
* tdp_common.py - instance format and helpers shared by paper_milp.py and gams_iqp.py (taken from exact_milp.py).
* gams_iqp.py - QMTDP / QCTDP IQP of the same paper, solved with GAMSPy/DICOPT (needs a GAMSPy license).
  Copied from D:\\territory problem\\Code\\NASE-Code, together with dicopt.opt.

Changes to the copies are marked with "project-2 patch". The adapters that feed the app's zones to
these codes live in backend/algorithm_comparison.py.
"""
