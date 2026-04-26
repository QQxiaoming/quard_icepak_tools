set table_columns [list metric_key metric_label minimum maximum unit interpretation]
puts [join [linsert $table_columns 0 "__QD_TABLE_COLUMNS__"] "\t"]

proc _metric_spec {metric_key} {
    switch -- $metric_key {
        det_aspect {
            return [list "Quality" "" "数值通常越大越好"]
        }
        skewness {
            return [list "Skewness" "" "数值通常越小越好"]
        }
        facealign {
            return [list "Face alignment" "" "数值通常越大越好"]
        }
        volume {
            return [list "Cell volume" "m^3" "应保持正值"]
        }
    }
    return [list $metric_key "" ""]
}

proc _emit_metric_row {metric_key min_value max_value} {
    lassign [_metric_spec $metric_key] metric_label unit interpretation
    puts [join [list \
        "__QD_TABLE_ROW__" \
        $metric_key \
        $metric_label \
        [format %.6g $min_value] \
        [format %.6g $max_value] \
        $unit \
        $interpretation] "\t"]
}

puts "=== Icepak mesh generation and quality evaluation ==="
puts "开始生成网格，请等待 ..."

if {[catch {
    grid_generate
} err opts]} {
    puts "网格生成失败：$err"
    if {[dict exists $opts -errorinfo]} {
        puts [dict get $opts -errorinfo]
    }
    exit 2
}

puts "网格生成完成，开始统计质量指标 ..."

global grid_quality_limits
foreach metric_key {det_aspect skewness facealign volume} {
    if {[catch {
        set min_value [grid_compute_quality $metric_key 0]
        set limits $grid_quality_limits($metric_key)
        set max_value [lindex $limits 1]
        _emit_metric_row $metric_key $min_value $max_value
    } err opts]} {
        puts "质量指标 $metric_key 统计失败：$err"
        if {[dict exists $opts -errorinfo]} {
            puts [dict get $opts -errorinfo]
        }
        exit 3
    }
}

if {[catch {auto_save_all} err opts]} {
    puts "警告：网格生成成功，但自动保存失败：$err"
    if {[dict exists $opts -errorinfo]} {
        puts [dict get $opts -errorinfo]
    }
}

puts "=== Mesh quality evaluation done ==="
exit 0