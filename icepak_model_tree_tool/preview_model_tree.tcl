set length_unit "m"
catch {
    global unit_default
    if {[info exists unit_default(length)] && $unit_default(length) != ""} {
        set length_unit $unit_default(length)
    }
}

puts "=== Icepak model tree preview ==="
puts [format "Length unit: %s" $length_unit]
puts "__QD_TABLE_COLUMNS__\tobject_type\tobject_name"

set model_objects [list]
foreach obj [db_list_objects_recursive] {
    if {[catch {set object_name [$obj getval name]}]} {
        continue
    }
    if {$object_name == ""} {
        continue
    }
    set material_library_path ""
    catch {set material_library_path [$obj getval mat_lib_path ""]}
    if {$material_library_path != ""} {
        continue
    }
    lappend model_objects $obj
}

set total_objects [llength $model_objects]
puts [join [list "__QD_PROGRESS__" "determinate" 0 [expr {$total_objects > 0 ? $total_objects : 1}] "正在收集 Icepak 模型对象..."] "\t"]

set index 0
foreach obj $model_objects {
    incr index
    puts [join [list "__QD_PROGRESS__" "determinate" $index [expr {$total_objects > 0 ? $total_objects : 1}] [format "正在处理模型对象 %d / %d" $index $total_objects]] "\t"]

    if {[catch {set object_type [$obj getval obtype]}]} {
        set object_type "unknown"
    }
    set object_name [$obj getval name]
    puts [join [list "__QD_TABLE_ROW__" $object_type $object_name] "\t"]
}

puts [format "=== Collected %d model objects ===" $total_objects]
puts [join [list "__QD_PROGRESS__" "determinate" [expr {$total_objects > 0 ? $total_objects : 1}] [expr {$total_objects > 0 ? $total_objects : 1}] "Icepak 模型树预览完成"] "\t"]
exit 0