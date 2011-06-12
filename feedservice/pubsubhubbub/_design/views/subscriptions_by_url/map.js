function(doc)
{
    if(doc.doc_type == "SubscribedFeed")
    {
        emit(doc.url, null);
    }
}
