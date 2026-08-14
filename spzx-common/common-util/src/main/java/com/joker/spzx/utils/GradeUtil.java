package com.joker.spzx.utils;

public class GradeUtil {

    public static String toGrade(Integer score) {
        if (score == null) return null;
        if (score == 100) return "S";
        if (score >= 95) return "A+";
        if (score >= 90) return "A";
        if (score >= 80) return "B";
        if (score >= 70) return "C";
        if (score >= 60) return "D";
        return "D-";
    }
}
