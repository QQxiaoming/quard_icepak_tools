proc _bbox_size {bbox} {
    if {[llength $bbox] != 2} {
        return ""
    }
    set pmin [lindex $bbox 0]
    set pmax [lindex $bbox 1]
    if {[llength $pmin] != 3 || [llength $pmax] != 3} {
        return ""
    }
    set xmin [lindex $pmin 0]
    set ymin [lindex $pmin 1]
    set zmin [lindex $pmin 2]
    set xmax [lindex $pmax 0]
    set ymax [lindex $pmax 1]
    set zmax [lindex $pmax 2]
    return [list \
        [expr {$xmax - $xmin}] \
        [expr {$ymax - $ymin}] \
        [expr {$zmax - $zmin}] \
        $xmin $xmax $ymin $ymax $zmin $zmax]
}

proc _convert_length {value unit_name} {
    if {$value == ""} {
        return ""
    }
    return [unit_convert $value $unit_name 1]
}

proc _shape_dims {shape} {
    set dims [list [$shape getval dim_x] [$shape getval dim_y] [$shape getval dim_z]]
    if {[catch {expr {[lindex $dims 0] + [lindex $dims 1] + [lindex $dims 2]}}]} {
        return ""
    }
    return $dims
}

set length_unit "m"
catch {
    global unit_default
    if {[info exists unit_default(length)] && $unit_default(length) != ""} {
        set length_unit $unit_default(length)
    }
}

puts "=== Icepak block dimensions ==="
puts [format "Length unit: %s" $length_unit]
puts "__QD_TABLE_COLUMNS__\tnode_id\tparent_id\tnode_kind\tobject_name\tobject_type\tshape_name\tshape_type\tdetail\tlength_unit\tdx\tdy\tdz\txmin\txmax\tymin\tymax\tzmin\tzmax"
set count 0
set block_object_count 0
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
puts [join [list "__QD_PROGRESS__" "determinate" 0 [expr {$total_objects > 0 ? $total_objects : 1}] "正在按模型树收集 block 尺寸..."] "\t"]

set object_index 0
foreach obj $model_objects {
    incr object_index
    puts [join [list "__QD_PROGRESS__" "determinate" $object_index [expr {$total_objects > 0 ? $total_objects : 1}] [format "正在处理模型对象 %d / %d" $object_index $total_objects]] "\t"]

    set object_type "unknown"
    catch {set object_type [$obj getval obtype]}
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

    set detail ""
    set dx ""
    set dy ""
    set dz ""
    set xmin ""
    set xmax ""
    set ymin ""
    set ymax ""
    set zmin ""
    set zmax ""

    if {$object_type == "block"} {
        set body_bbox ""
        catch {set body_bbox [[$obj getval body_shape] get_bbox]}
        set body_size [_bbox_size $body_bbox]
        if {$body_size != ""} {
            set dx [_convert_length [lindex $body_size 0] $length_unit]
            set dy [_convert_length [lindex $body_size 1] $length_unit]
            set dz [_convert_length [lindex $body_size 2] $length_unit]
            set xmin [_convert_length [lindex $body_size 3] $length_unit]
            set xmax [_convert_length [lindex $body_size 4] $length_unit]
            set ymin [_convert_length [lindex $body_size 5] $length_unit]
            set ymax [_convert_length [lindex $body_size 6] $length_unit]
            set zmin [_convert_length [lindex $body_size 7] $length_unit]
            set zmax [_convert_length [lindex $body_size 8] $length_unit]
            set detail [format "包围盒: dx=%s dy=%s dz=%s" $dx $dy $dz]
        } else {
            set detail "block 包围盒不可用"
        }
        incr block_object_count
    }

    puts [join [list \
        "__QD_TABLE_ROW__" \
        $obj \
        $parent_id \
        "object" \
        $object_name \
        $object_type \
        "" \
        "" \
        $detail \
        [expr {$object_type == "block" ? $length_unit : ""}] \
        $dx \
        $dy \
        $dz \
        $xmin \
        $xmax \
        $ymin \
        $ymax \
        $zmin \
        $zmax] "\t"]

    set shapes [db_shapes $obj]
    if {[llength $shapes] <= 1} {
        continue
    }

    foreach sh $shapes {
        set shape_name [$sh get -name]
        if {$object_type == "network"} {
            set shape_name [$obj getval ${shape_name}_name ${shape_name}]
        }

        set shape_type [$sh get -shtype]
        set shape_detail ""
        set shape_dx ""
        set shape_dy ""
        set shape_dz ""
        set shape_unit ""

        if {$object_type == "block" && $shape_type != "container"} {
            set dims [_shape_dims $sh]
            if {$dims != ""} {
                set shape_dx [_convert_length [lindex $dims 0] $length_unit]
                set shape_dy [_convert_length [lindex $dims 1] $length_unit]
                set shape_dz [_convert_length [lindex $dims 2] $length_unit]
                set shape_unit $length_unit
                set shape_detail [format "shape 尺寸: dx=%s dy=%s dz=%s" $shape_dx $shape_dy $shape_dz]
                incr count
            }
        }

        puts [join [list \
            "__QD_TABLE_ROW__" \
            $sh \
            $obj \
            "shape" \
            $shape_name \
            $shape_type \
            $shape_name \
            $shape_type \
            $shape_detail \
            $shape_unit \
            $shape_dx \
            $shape_dy \
            $shape_dz \
            "" \
            "" \
            "" \
            "" \
            "" \
            ""] "\t"]
    }
}

puts [format "=== Collected %d block shape records from %d block objects ===" $count $block_object_count]
puts [join [list "__QD_PROGRESS__" "determinate" [expr {$total_objects > 0 ? $total_objects : 1}] [expr {$total_objects > 0 ? $total_objects : 1}] "Block 尺寸统计完成"] "\t"]
exit 0
