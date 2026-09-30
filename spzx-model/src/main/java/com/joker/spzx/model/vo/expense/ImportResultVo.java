package com.joker.spzx.model.vo.expense;

import lombok.Data;

import java.util.ArrayList;
import java.util.List;

@Data
public class ImportResultVo {

    /** 文件数据行总数（表头之后） */
    private int total;

    /** 新导入笔数 */
    private int imported;

    /** 交易号重复跳过 */
    private int skippedDuplicate;

    /** 非支出行跳过（收入/不计收支） */
    private int skippedNonExpense;

    /** 交易关闭跳过 */
    private int skippedClosed;

    /** 金额为 0 的支出行跳过 */
    private int skippedZero;

    /** 已关账月份跳过（先关账再导新账单时，旧月行不再写入） */
    private int skippedClosedPeriod;

    /** 解析失败明细（行号+原因） */
    private List<String> errors = new ArrayList<>();
}
