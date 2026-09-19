"""面向实验人员的输入与几何错误。"""


class DataContractError(ValueError):
    """CSV 或 metadata 不符合已声明的数据契约。"""


class ReconstructionError(ValueError):
    """圆桶参考不足、退化或质量不达标，不能可靠重建。"""
