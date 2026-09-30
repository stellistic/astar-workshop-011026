let
    Source = Lakehouse.Contents([HierarchicalNavigation = null, EnableVorder = true, OutputMetadataRefresh = true]),
    #"Navigation 1" = Source{[workspaceId = "."]}[Data],
    #"Navigation 2" = #"Navigation 1"{[lakehouseName = "lh_kcorp_plant"]}[Data],
    #"Navigation 3" = #"Navigation 2"{[Id = "bronze.dim_customer", ItemKind = "Table"]}[Data],
    #"Choose columns" = Table.SelectColumns(#"Navigation 3", {"CustomerKey", "CustomerName", "Industry", "Segment", "Region", "Country"}),
    #"Trimmed text" = Table.TransformColumns(#"Choose columns", {{"CustomerName", Text.Trim, type text}, {"Industry", Text.Trim, type text}, {"Segment", Text.Trim, type text}, {"Region", Text.Trim, type text}, {"Country", Text.Trim, type text}}),
    #"Replaced SG" = Table.ReplaceValue(#"Trimmed text", "SG", "Singapore", Replacer.ReplaceValue, {"Country"}),
    #"Replaced MY" = Table.ReplaceValue(#"Replaced SG", "MY", "Malaysia", Replacer.ReplaceValue, {"Country"}),
    #"Replaced IN" = Table.ReplaceValue(#"Replaced MY", "IN", "India", Replacer.ReplaceValue, {"Country"}),
    #"Replaced AU" = Table.ReplaceValue(#"Replaced IN", "AU", "Australia", Replacer.ReplaceValue, {"Country"}),
    #"Capitalized each word" = Table.TransformColumns(#"Replaced AU", {{"Country", Text.Proper, type text}}),
    #"Changed column type" = Table.TransformColumnTypes(#"Capitalized each word", {{"CustomerKey", Int64.Type}}),
    #"Removed duplicates" = Table.Distinct(#"Changed column type", {"CustomerKey"})
in
    #"Removed duplicates"
