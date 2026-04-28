set length_unit "m"
catch {
    global unit_default
    if {[info exists unit_default(length)] && $unit_default(length) != ""} {
        set length_unit $unit_default(length)
    }
}

puts "=== Icepak model tree preview ==="
puts [format "Length unit: %s" $length_unit]
puts "__QD_TABLE_COLUMNS__\tnode_id\tparent_id\tnode_kind\tobject_type\tobject_name\tdetail"

set model_objects [list]
foreach obj [db_list_objects_recursive] {
    if {[catch {set object_name [$obj getval name]}]} {
        continue
    }
    if {$object_name == ""} {
        continue
    }
    set object_type "unknown"
    catch {set object_type [$obj getval obtype]}
    if {$object_type == "material"} {
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

    if {$object_type == "domain"} {
        set object_name "Domain"
    } else {
        set object_name [$obj getval name]
    }

    set parent_id "__root__"
    catch {set parent_id [$obj get -model_container]}
    if {$parent_id == ""} {
        set parent_id "__root__"
    }

    puts [join [list "__QD_TABLE_ROW__" $obj $parent_id "object" $object_type $object_name ""] "\t"]

    set shapes [db_shapes $obj]
    if {[llength $shapes] > 1} {
        foreach sh $shapes {
            set shape_name [$sh get -name]
            if {$object_type == "network"} {
                set shape_name [$obj getval ${shape_name}_name ${shape_name}]
            }
            set shape_type [$sh get -shtype]
            puts [join [list "__QD_TABLE_ROW__" $sh $obj "shape" $shape_type $shape_name ""] "\t"]
        }
    }
}

puts [format "=== Collected %d model objects ===" $total_objects]
puts [join [list "__QD_PROGRESS__" "determinate" [expr {$total_objects > 0 ? $total_objects : 1}] [expr {$total_objects > 0 ? $total_objects : 1}] "Icepak 模型树预览完成"] "\t"]
exit 0