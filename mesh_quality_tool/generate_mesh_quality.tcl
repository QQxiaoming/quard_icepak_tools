set table_columns [list metric_key metric_label minimum maximum unit interpretation]
puts [join [linsert $table_columns 0 "__QD_TABLE_COLUMNS__"] "\t"]

proc _emit_context {category key label value {unit ""}} {
    puts [join [list "__QD_CONTEXT__" $category $key $label $value $unit] "\t"]
}

proc _emit_progress {mode value maximum message} {
    puts [join [list "__QD_PROGRESS__" $mode $value $maximum $message] "\t"]
}

proc _apply_env_override {env_key variable_name label} {
    global env
    upvar #0 $variable_name target

    if {![info exists env($env_key)]} {
        return
    }

    set raw_value [string trim $env($env_key)]
    if {$raw_value eq ""} {
        return
    }

    set target $raw_value
    puts "应用用户参数: $label = $raw_value"
}

proc _apply_mesh_overrides {} {
    global grid_size_x grid_size_y grid_size_z
    global grid_sep_x grid_sep_y grid_sep_z
    global grid_max_elements grid_tetra_smqual grid_tetra_smiters
    global grid_enable_prism_layer grid_tetra_prism_num
    global grid_hdm_feature_angle grid_hdm_refine_features grid_include_all_gaps

    _apply_env_override "QUARD_ICEPAK_GRID_SIZE_X" grid_size_x "全局尺寸 X"
    _apply_env_override "QUARD_ICEPAK_GRID_SIZE_Y" grid_size_y "全局尺寸 Y"
    _apply_env_override "QUARD_ICEPAK_GRID_SIZE_Z" grid_size_z "全局尺寸 Z"
    _apply_env_override "QUARD_ICEPAK_GRID_SEP_X" grid_sep_x "最小分离间隙 X"
    _apply_env_override "QUARD_ICEPAK_GRID_SEP_Y" grid_sep_y "最小分离间隙 Y"
    _apply_env_override "QUARD_ICEPAK_GRID_SEP_Z" grid_sep_z "最小分离间隙 Z"
    _apply_env_override "QUARD_ICEPAK_GRID_MAX_ELEMENTS" grid_max_elements "最大单元数"
    _apply_env_override "QUARD_ICEPAK_GRID_TETRA_SMQUAL" grid_tetra_smqual "平滑质量阈值"
    _apply_env_override "QUARD_ICEPAK_GRID_TETRA_SMITERS" grid_tetra_smiters "平滑迭代次数"
    _apply_env_override "QUARD_ICEPAK_GRID_ENABLE_PRISM_LAYER" grid_enable_prism_layer "启用棱柱层"
    _apply_env_override "QUARD_ICEPAK_GRID_TETRA_PRISM_NUM" grid_tetra_prism_num "棱柱层数"
    _apply_env_override "QUARD_ICEPAK_GRID_HDM_FEATURE_ANGLE" grid_hdm_feature_angle "特征角"
    _apply_env_override "QUARD_ICEPAK_GRID_HDM_REFINE_FEATURES" grid_hdm_refine_features "启用特征细化"
    _apply_env_override "QUARD_ICEPAK_GRID_INCLUDE_ALL_GAPS" grid_include_all_gaps "包含全部窄缝"
}

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

proc _emit_model_and_mesh_context {} {
    global grid_type grid_settings_type grid_size_x grid_size_y grid_size_z
    global grid_sep_x grid_sep_y grid_sep_z grid_sep_x_units grid_sep_y_units grid_sep_z_units
    global grid_max_elements grid_tetra_smqual grid_tetra_smiters grid_enable_prism_layer
    global grid_tetra_prism_num grid_hdm_feature_angle grid_hdm_refine_features
    global grid_include_all_gaps meshing_units

    _emit_context mesh grid_type "网格类型" $grid_type ""
    _emit_context mesh grid_settings_type "网格设置档位" $grid_settings_type ""
    _emit_context mesh grid_size_x "全局尺寸 X" $grid_size_x $meshing_units
    _emit_context mesh grid_size_y "全局尺寸 Y" $grid_size_y $meshing_units
    _emit_context mesh grid_size_z "全局尺寸 Z" $grid_size_z $meshing_units
    _emit_context mesh grid_sep_x "最小分离间隙 X" $grid_sep_x $grid_sep_x_units
    _emit_context mesh grid_sep_y "最小分离间隙 Y" $grid_sep_y $grid_sep_y_units
    _emit_context mesh grid_sep_z "最小分离间隙 Z" $grid_sep_z $grid_sep_z_units
    _emit_context mesh grid_max_elements "最大单元数" $grid_max_elements ""
    _emit_context mesh grid_tetra_smqual "平滑质量阈值" $grid_tetra_smqual ""
    _emit_context mesh grid_tetra_smiters "平滑迭代次数" $grid_tetra_smiters ""
    _emit_context mesh grid_enable_prism_layer "棱柱层开关" $grid_enable_prism_layer ""
    _emit_context mesh grid_tetra_prism_num "棱柱层数" $grid_tetra_prism_num ""
    _emit_context mesh grid_hdm_feature_angle "特征角" $grid_hdm_feature_angle "deg"
    _emit_context mesh grid_hdm_refine_features "特征细化开关" $grid_hdm_refine_features ""
    _emit_context mesh grid_include_all_gaps "全部窄缝包含开关" $grid_include_all_gaps ""

    set object_count 0
    set block_count 0
    foreach obj [db_list_objects_recursive] {
        incr object_count
        if {[catch {set obtype [$obj getval obtype]}]} {
            continue
        }
        if {$obtype == "block"} {
            incr block_count
        }
    }
    _emit_context model object_count "模型对象数" $object_count ""
    _emit_context model block_count "block 数" $block_count ""
}

puts "=== Icepak mesh generation and quality evaluation ==="
puts "开始生成网格，请等待 ..."

_apply_mesh_overrides
_emit_model_and_mesh_context
_emit_progress determinate 5 100 "已读取模型与网格参数"
_emit_progress indeterminate 0 0 "正在生成网格..."

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
_emit_progress determinate 70 100 "网格生成完成，开始评估质量"

global grid_quality_limits
set metric_keys {det_aspect skewness facealign volume}
set metric_total [llength $metric_keys]
set metric_index 0
foreach metric_key $metric_keys {
    incr metric_index
    set progress_value [expr {70 + int(24.0 * $metric_index / $metric_total)}]
    _emit_progress determinate $progress_value 100 [format "正在评估质量指标 %d / %d" $metric_index $metric_total]
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
_emit_progress determinate 99 100 "网格质量评估完成，正在整理结果..."
exit 0