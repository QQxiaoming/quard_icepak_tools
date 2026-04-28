proc _load_mesh_refinement_rules {} {
    global env quard_mesh_refinement_rules

    set quard_mesh_refinement_rules [list]
    if {![info exists env(QUARD_ICEPAK_MESH_RULES_FILE)]} {
        return
    }

    set rules_file [string trim $env(QUARD_ICEPAK_MESH_RULES_FILE)]
    if {$rules_file eq ""} {
        return
    }
    if {![file exists $rules_file]} {
        error [format "mesh refinement rules file not found: %s" $rules_file]
    }

    source $rules_file
}

proc _rule_matches_name {match_mode patterns object_name} {
    foreach pattern $patterns {
        if {$match_mode eq "exact"} {
            if {$object_name eq $pattern} {
                return 1
            }
            continue
        }
        if {$match_mode eq "regex"} {
            if {[regexp -- $pattern $object_name]} {
                return 1
            }
            continue
        }
        if {[string match $pattern $object_name]} {
            return 1
        }
    }
    return 0
}

proc _emit_rule_preview {name priority match_mode patterns matched_names} {
    puts [join [list \
        "__QD_PREVIEW_RULE__" \
        $name \
        $priority \
        $match_mode \
        [join $patterns "|"] \
        [llength $matched_names]] "\t"]
    foreach object_name $matched_names {
        puts [join [list "__QD_PREVIEW_MATCH__" $name $object_name] "\t"]
    }
}

puts "=== Icepak mesh refinement preview ==="
_load_mesh_refinement_rules

if {![info exists quard_mesh_refinement_rules] || [llength $quard_mesh_refinement_rules] == 0} {
    error "no mesh refinement rules configured"
}

set block_names [list]
foreach obj [db_list_objects_recursive] {
    if {[catch {set obtype [$obj getval obtype]}]} {
        continue
    }
    if {$obtype ne "block"} {
        continue
    }
    lappend block_names [$obj getval name]
}

foreach rule $quard_mesh_refinement_rules {
    if {![dict get $rule enabled]} {
        continue
    }

    set name [dict get $rule name]
    set priority [dict get $rule priority]
    set match_mode [dict get $rule match_mode]
    set patterns [dict get $rule patterns]
    set matched_names [list]
    foreach object_name $block_names {
        if {[_rule_matches_name $match_mode $patterns $object_name]} {
            lappend matched_names $object_name
        }
    }
    _emit_rule_preview $name $priority $match_mode $patterns $matched_names
}

exit 0