let
    Source = Lakehouse.Contents([HierarchicalNavigation = null, EnableVorder = true, OutputMetadataRefresh = true]),
    #"Navigation 1" = Source{[workspaceId = "."]}[Data],
    #"Navigation 2" = #"Navigation 1"{[lakehouseName = "lh_kcorp_plant"]}[Data],
    #"Navigation 3" = #"Navigation 2"{[Id = "bronze.dim_product", ItemKind = "Table"]}[Data],
    #"Choose columns" = Table.SelectColumns(#"Navigation 3", {"ProductKey", "ProductCode", "ProductName", "ProductFamily", "Category", "UnitPrice", "StandardCost"}),
    #"Trimmed text" = Table.TransformColumns(#"Choose columns", {{"ProductName", each Text.Trim(_), type nullable text}}),
    #"Capitalized each word" = Table.TransformColumns(#"Trimmed text", {{"Category", each Text.Proper(_), type nullable text}}),
    #"Replaced value" = Table.ReplaceValue(#"Capitalized each word", "$", "", Replacer.ReplaceText, {"UnitPrice"}),
    #"Replaced value 1" = Table.ReplaceValue(#"Replaced value", ",", "", Replacer.ReplaceText, {"UnitPrice"}),
    #"Changed column type" = Table.TransformColumnTypes(#"Replaced value 1", {{"ProductKey", Int64.Type}, {"StandardCost", type number}, {"UnitPrice", type number}}),
    #"Removed duplicates" = Table.Distinct(#"Changed column type", {"ProductKey"})
in
    #"Removed duplicates"
