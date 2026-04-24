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

puts "=== Icepak block dimensions for paired dz adjustment ==="
puts [format "Length unit: %s" $length_unit]
puts "__QD_TABLE_COLUMNS__\tobject_name\tobject_type\tshape_name\tshape_type\tlength_unit\tdx\tdy\tdz\txmin\txmax\tymin\tymax\tzmin\tzmax"

set count 0
foreach obj [db_list_objects_recursive] {
    if {[$obj getval mat_lib_path ""] != ""} {
        continue
    }
    if {[$obj getval obtype] != "block"} {
        continue
    }

    set obj_name [$obj getval name]
    set body_bbox ""
    catch {set body_bbox [[$obj getval body_shape] get_bbox]}
    set body_size [_bbox_size $body_bbox]

    foreach sh [db_shapes $obj] {
        if {[$sh get -shtype] == "container"} {
            continue
        }

        set dims [_shape_dims $sh]
        if {$dims == ""} {
            continue
        }

        set dx [_convert_length [lindex $dims 0] $length_unit]
        set dy [_convert_length [lindex $dims 1] $length_unit]
        set dz [_convert_length [lindex $dims 2] $length_unit]

        if {$body_size == ""} {
            set xmin ""
            set xmax ""
            set ymin ""
            set ymax ""
            set zmin ""
            set zmax ""
        } else {
            set xmin [_convert_length [lindex $body_size 3] $length_unit]
            set xmax [_convert_length [lindex $body_size 4] $length_unit]
            set ymin [_convert_length [lindex $body_size 5] $length_unit]
            set ymax [_convert_length [lindex $body_size 6] $length_unit]
            set zmin [_convert_length [lindex $body_size 7] $length_unit]
            set zmax [_convert_length [lindex $body_size 8] $length_unit]
        }

        puts [join [list \
            "__QD_TABLE_ROW__" \
            $obj_name \
            [$obj getval obtype] \
            [$sh get -name] \
            [$sh get -shtype] \
            $length_unit \
            $dx \
            $dy \
            $dz \
            $xmin \
            $xmax \
            $ymin \
            $ymax \
            $zmin \
            $zmax] "\t"]
        incr count
    }
}

puts [format "=== Collected %d shape records ===" $count]
exit 0